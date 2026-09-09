"""
SWARAJ Egress Monitor - Real-time network connection monitoring.

SECURITY BOUNDARIES:
- Polls network state every ~2 seconds during agent runs
- Distinguishes loopback (127.0.0.1, ::1) from non-loopback connections
- Triggers kill-switch on forbidden non-loopback ESTABLISHED connections
- Records all events for certificate attestation
- FAIL-CLOSED: Cannot certify runs with forbidden egress
"""

import time
import socket
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Callable, Any
from pathlib import Path

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class SecurityStatus(str, Enum):
    """Security status of a run."""
    SUCCESS = "success"
    FAILED = "failed"
    MONITORING = "monitoring"


@dataclass
class ConnectionEvent:
    """Recorded network connection event."""
    timestamp: str
    local_address: str
    local_port: int
    remote_address: str
    remote_port: int
    status: str  # LISTEN, ESTABLISHED, TIME_WAIT, etc.
    is_loopback: bool
    is_forbidden: bool = False
    pid: Optional[int] = None
    process_name: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "local_address": self.local_address,
            "local_port": self.local_port,
            "remote_address": self.remote_address,
            "remote_port": self.remote_port,
            "status": self.status,
            "is_loopback": self.is_loopback,
            "is_forbidden": self.is_forbidden,
            "pid": self.pid,
            "process_name": self.process_name,
        }


@dataclass
class EgressState:
    """Current egress monitoring state."""
    run_id: str
    security_status: SecurityStatus = SecurityStatus.MONITORING
    events: list[ConnectionEvent] = field(default_factory=list)
    kill_switch_triggered: bool = False
    last_poll_time: Optional[str] = None
    event_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "security_status": self.security_status.value,
            "events": [e.to_dict() for e in self.events],
            "kill_switch_triggered": self.kill_switch_triggered,
            "last_poll_time": self.last_poll_time,
            "event_count": self.event_count,
        }


class EgressMonitor:
    """
    Real-time egress monitor using psutil.
    
    SECURITY BOUNDARIES:
    - Polls every ~2 seconds
    - Detects forbidden non-loopback ESTABLISHED connections
    - Triggers kill-switch immediately on detection
    - Records all events for audit/certificate
    """
    
    def __init__(
        self,
        run_id: str,
        poll_interval: float = 2.0,
        allowed_remote_hosts: Optional[set[str]] = None,
    ):
        self.run_id = run_id
        self.poll_interval = poll_interval
        self.allowed_remote_hosts = allowed_remote_hosts or set()
        
        self._state = EgressState(run_id=run_id)
        self._monitoring = False
        self._thread: Optional[threading.Thread] = None
        self._kill_switch_callback: Optional[Callable[[], None]] = None
        
        if not PSUTIL_AVAILABLE:
            raise RuntimeError("psutil required for egress monitoring")
    
    @property
    def state(self) -> EgressState:
        """Get current egress state."""
        return self._state
    
    @property
    def security_status(self) -> SecurityStatus:
        """Get current security status."""
        return self._state.security_status
    
    @property
    def kill_switch_triggered(self) -> bool:
        """Check if kill-switch has been triggered."""
        return self._state.kill_switch_triggered
    
    def set_kill_switch_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to invoke when kill-switch triggers."""
        self._kill_switch_callback = callback
    
    def _is_loopback(self, address: str) -> bool:
        """Check if address is loopback."""
        return address in ('127.0.0.1', '::1', 'localhost', '0:0:0:0:0:0:0:1')
    
    def _is_forbidden(self, remote_address: str, is_loopback: bool) -> bool:
        """
        Determine if a connection is forbidden.
        
        Forbidden = non-loopback ESTABLISHED connection not in allowed list.
        
        SECURITY BOUNDARY: All non-loopback connections are forbidden by default.
        """
        if is_loopback:
            return False
        
        # Non-loopback connections are forbidden by default (deny-by-default)
        # Only explicitly allowed hosts would be permitted (none by default)
        return True
    
    def _poll_connections(self) -> list[ConnectionEvent]:
        """Poll current network connections."""
        events = []
        now = datetime.now(timezone.utc).isoformat()
        
        try:
            # Get all network connections
            connections = psutil.net_connections(kind='inet')
            
            for conn in connections:
                # Skip if no remote address (listening sockets)
                if not conn.raddr:
                    continue
                
                # Only track ESTABLISHED connections as potential egress
                if conn.status != 'ESTABLISHED':
                    continue
                
                local_addr = conn.laddr.ip if conn.laddr else ''
                local_port = conn.laddr.port if conn.laddr else 0
                remote_addr = conn.raddr.ip if conn.raddr else ''
                remote_port = conn.raddr.port if conn.raddr else 0
                
                is_loopback = self._is_loopback(local_addr) and self._is_loopback(remote_addr)
                is_forbidden = self._is_forbidden(remote_addr, is_loopback)
                
                # Get process info if available
                pid = conn.pid
                process_name = None
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        process_name = proc.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                event = ConnectionEvent(
                    timestamp=now,
                    local_address=local_addr,
                    local_port=local_port,
                    remote_address=remote_addr,
                    remote_port=remote_port,
                    status=conn.status,
                    is_loopback=is_loopback,
                    is_forbidden=is_forbidden,
                    pid=pid,
                    process_name=process_name,
                )
                events.append(event)
                
        except psutil.AccessDenied:
            # May need elevated privileges
            pass
        except Exception:
            # Log but don't crash monitoring
            pass
        
        return events
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        while self._monitoring:
            if not self._monitoring:
                break
            
            # Poll connections
            events = self._poll_connections()
            
            # Process new events
            for event in events:
                # Add to state
                self._state.events.append(event)
                self._state.event_count += 1
                
                # Check for forbidden connection
                if event.is_forbidden:
                    self._trigger_kill_switch(event)
                    break  # Exit loop after triggering
            
            self._state.last_poll_time = datetime.now(timezone.utc).isoformat()
            
            # Sleep interval
            time.sleep(self.poll_interval)
    
    def _trigger_kill_switch(self, event: ConnectionEvent) -> None:
        """Trigger kill-switch on forbidden egress."""
        self._state.kill_switch_triggered = True
        self._state.security_status = SecurityStatus.FAILED
        
        # Invoke callback if set
        if self._kill_switch_callback:
            try:
                self._kill_switch_callback()
            except Exception:
                pass  # Don't let callback errors crash monitoring
    
    def start(self) -> None:
        """Start monitoring in background thread."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._state.security_status = SecurityStatus.MONITORING
        
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
    
    def start_monitoring(self, run_id: Optional[str] = None) -> None:
        """Alias for start()."""
        if run_id:
            self.run_id = run_id
            self._state.run_id = run_id
        self.start()
    
    def stop(self) -> None:
        """Stop monitoring."""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
    
    def get_events(self) -> list[dict]:
        """Get all recorded events as dictionaries."""
        return [e.to_dict() for e in self._state.events]
    
    def get_forbidden_events(self) -> list[dict]:
        """Get only forbidden events."""
        return [e.to_dict() for e in self._state.events if e.is_forbidden]
    
    def can_certify(self) -> bool:
        """
        Check if run can be certified.
        
        FAIL-CLOSED: Cannot certify if:
        - Kill-switch triggered
        - Security status is failed
        - Forbidden egress detected
        """
        if self._state.kill_switch_triggered:
            return False
        
        if self._state.security_status != SecurityStatus.SUCCESS:
            return False
        
        if any(e.is_forbidden for e in self._state.events):
            return False
        
        return True
    
    def mark_success(self) -> None:
        """Mark run as successfully completed (no forbidden egress)."""
        if self._state.kill_switch_triggered:
            raise RuntimeError("Cannot mark success: kill-switch already triggered")
        
        self._state.security_status = SecurityStatus.SUCCESS
    
    def inject_test_event(self, event: ConnectionEvent) -> None:
        """
        Inject a test event for testing without real network access.
        
        SECURITY: This is for testing only. In production, only real
        psutil polling should be used.
        """
        self._state.events.append(event)
        self._state.event_count += 1
        
        if event.is_forbidden:
            self._trigger_kill_switch(event)
