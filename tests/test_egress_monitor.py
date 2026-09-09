"""Tests for SWARAJ Egress Monitor - Network connection monitoring."""

import pytest
from datetime import datetime, timezone

from swaraj.monitor.egress_watch import (
    EgressMonitor,
    ConnectionEvent,
    EgressState,
    SecurityStatus,
)


@pytest.fixture
def egress_monitor():
    """Create EgressMonitor instance."""
    return EgressMonitor(run_id="test-run-123", poll_interval=0.5)


class TestLoopbackAllowance:
    """Test that loopback connections don't trigger security failure."""
    
    def test_loopback_event_not_forbidden(self, egress_monitor):
        """Loopback connections are not marked as forbidden."""
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="127.0.0.1",
            local_port=8080,
            remote_address="127.0.0.1",
            remote_port=9090,
            status="ESTABLISHED",
            is_loopback=True,
        )
        
        egress_monitor.inject_test_event(event)
        
        assert not event.is_forbidden
        assert len(egress_monitor.get_forbidden_events()) == 0
    
    def test_localhost_connection_allowed(self, egress_monitor):
        """Localhost connections are allowed."""
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="localhost",
            local_port=8080,
            remote_address="localhost",
            remote_port=9090,
            status="ESTABLISHED",
            is_loopback=True,
        )
        
        egress_monitor.inject_test_event(event)
        
        assert not event.is_forbidden


class TestNonLoopbackDetection:
    """Test detection of forbidden non-loopback connections."""
    
    def test_external_ip_forbidden(self, egress_monitor):
        """External IP addresses are forbidden."""
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="192.168.1.100",
            local_port=54321,
            remote_address="8.8.8.8",
            remote_port=53,
            status="ESTABLISHED",
            is_loopback=False,
        )
        
        # Compute is_forbidden flag using the monitor's logic
        event.is_forbidden = egress_monitor._is_forbidden(event.remote_address, event.is_loopback)
        
        egress_monitor.inject_test_event(event)
        
        assert event.is_forbidden
        assert len(egress_monitor.get_forbidden_events()) == 1
    
    def test_public_dns_forbidden(self, egress_monitor):
        """Public DNS servers are forbidden."""
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="10.0.0.5",
            local_port=12345,
            remote_address="1.1.1.1",
            remote_port=53,
            status="ESTABLISHED",
            is_loopback=False,
        )
        
        # Compute is_forbidden flag using the monitor's logic
        event.is_forbidden = egress_monitor._is_forbidden(event.remote_address, event.is_loopback)
        
        egress_monitor.inject_test_event(event)
        
        assert event.is_forbidden


class TestKillSwitch:
    """Test kill-switch behavior."""
    
    def test_kill_switch_triggered_on_forbidden(self, egress_monitor):
        """Kill-switch triggers when forbidden connection detected."""
        callback_called = False
        
        def callback():
            nonlocal callback_called
            callback_called = True
        
        egress_monitor.set_kill_switch_callback(callback)
        
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="192.168.1.100",
            local_port=54321,
            remote_address="8.8.8.8",
            remote_port=443,
            status="ESTABLISHED",
            is_loopback=False,
            is_forbidden=True,
        )
        
        egress_monitor.inject_test_event(event)
        
        assert egress_monitor.kill_switch_triggered is True
        assert callback_called is True
    
    def test_security_status_failed_after_kill_switch(self, egress_monitor):
        """Security status becomes FAILED after kill-switch."""
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="192.168.1.100",
            local_port=54321,
            remote_address="8.8.8.8",
            remote_port=443,
            status="ESTABLISHED",
            is_loopback=False,
            is_forbidden=True,
        )
        
        egress_monitor.inject_test_event(event)
        
        assert egress_monitor.security_status == SecurityStatus.FAILED


class TestCertificationEligibility:
    """Test certification eligibility checks."""
    
    def test_can_certify_clean_run(self, egress_monitor):
        """Clean runs can be certified."""
        # Add only loopback events
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="127.0.0.1",
            local_port=8080,
            remote_address="127.0.0.1",
            remote_port=9090,
            status="ESTABLISHED",
            is_loopback=True,
        )
        
        egress_monitor.inject_test_event(event)
        egress_monitor.mark_success()
        
        assert egress_monitor.can_certify() is True
    
    def test_cannot_certify_with_forbidden_egress(self, egress_monitor):
        """Runs with forbidden egress cannot be certified."""
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="192.168.1.100",
            local_port=54321,
            remote_address="8.8.8.8",
            remote_port=443,
            status="ESTABLISHED",
            is_loopback=False,
            is_forbidden=True,
        )
        
        egress_monitor.inject_test_event(event)
        
        assert egress_monitor.can_certify() is False
    
    def test_cannot_certify_killed_run(self, egress_monitor):
        """Killed runs cannot be certified."""
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="192.168.1.100",
            local_port=54321,
            remote_address="8.8.8.8",
            remote_port=443,
            status="ESTABLISHED",
            is_loopback=False,
            is_forbidden=True,
        )
        
        egress_monitor.inject_test_event(event)
        
        assert egress_monitor.can_certify() is False
    
    def test_cannot_mark_success_after_kill(self, egress_monitor):
        """Cannot mark success after kill-switch triggered."""
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="192.168.1.100",
            local_port=54321,
            remote_address="8.8.8.8",
            remote_port=443,
            status="ESTABLISHED",
            is_loopback=False,
            is_forbidden=True,
        )
        
        egress_monitor.inject_test_event(event)
        
        with pytest.raises(RuntimeError):
            egress_monitor.mark_success()


class TestEgressState:
    """Test egress state tracking."""
    
    def test_state_contains_run_id(self, egress_monitor):
        """State contains run ID."""
        state = egress_monitor.state
        
        assert state.run_id == "test-run-123"
    
    def test_state_serializable(self, egress_monitor):
        """State can be serialized to dict."""
        state_dict = egress_monitor.state.to_dict()
        
        assert "run_id" in state_dict
        assert "security_status" in state_dict
        assert "events" in state_dict
        assert "kill_switch_triggered" in state_dict
        assert "event_count" in state_dict
    
    def test_events_recorded(self, egress_monitor):
        """Events are recorded in state."""
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            local_address="127.0.0.1",
            local_port=8080,
            remote_address="127.0.0.1",
            remote_port=9090,
            status="ESTABLISHED",
            is_loopback=True,
        )
        
        egress_monitor.inject_test_event(event)
        
        events = egress_monitor.get_events()
        
        assert len(events) == 1
        assert events[0]["local_address"] == "127.0.0.1"
