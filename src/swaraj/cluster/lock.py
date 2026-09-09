"""
Distributed Lock implementation using Redis RedLock algorithm.

Provides mutual exclusion across multiple SWARAJ nodes for:
- Run ID uniqueness
- Certificate signing serialization
- Audit log consistency
"""

import time
import uuid
from typing import Optional
from dataclasses import dataclass

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class LockError(Exception):
    """Raised when lock acquisition fails."""
    pass


@dataclass
class DistributedLock:
    """
    Distributed lock using Redis RedLock algorithm.
    
    Usage:
        lock = DistributedLock(redis_hosts=["redis1", "redis2", "redis3"])
        with lock.acquire("run-123", timeout_ms=5000):
            # Critical section - only one node can hold this lock
            execute_run()
    """
    
    redis_hosts: list[str]
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    def __post_init__(self):
        if not REDIS_AVAILABLE:
            raise ImportError(
                "Redis package required for distributed locking. "
                "Install with: pip install redis"
            )
        
        self.clients = []
        for host in self.redis_hosts:
            client = redis.Redis(
                host=host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                socket_timeout=0.5,
                socket_connect_timeout=0.5,
            )
            self.clients.append(client)
    
    def acquire(self, resource: str, timeout_ms: int = 5000) -> "_LockContext":
        """
        Attempt to acquire lock on resource.
        
        Args:
            resource: Unique resource name (e.g., run ID, cert key)
            timeout_ms: Maximum time to wait for lock
            
        Returns:
            _LockContext manager
            
        Raises:
            LockError: If lock cannot be acquired within timeout
        """
        lock_id = str(uuid.uuid4())
        acquired = self._acquire_lock(resource, lock_id, timeout_ms)
        
        if not acquired:
            raise LockError(f"Failed to acquire lock on {resource} within {timeout_ms}ms")
        
        return _LockContext(self, resource, lock_id, timeout_ms)
    
    def _acquire_lock(self, resource: str, lock_id: str, timeout_ms: int) -> bool:
        """RedLock algorithm implementation."""
        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0
        
        n = len(self.clients)
        acquired_count = 0
        
        # Try to acquire lock on all nodes
        for client in self.clients:
            try:
                # Set NX (only if not exists), EX (expiry in seconds)
                expiry_sec = timeout_sec + 0.01  # Small buffer
                if client.set(resource, lock_id, nx=True, ex=expiry_sec):
                    acquired_count += 1
            except redis.RedisError:
                # Node unavailable, continue with others
                continue
        
        elapsed = time.time() - start_time
        
        # Lock acquired if majority of nodes agree AND within timeout
        quorum = (n // 2) + 1
        if acquired_count >= quorum and elapsed < timeout_sec:
            return True
        
        # Failed to acquire, release any partial locks
        self._release_lock(resource, lock_id)
        return False
    
    def _release_lock(self, resource: str, lock_id: str) -> None:
        """Release lock from all nodes."""
        # Lua script to ensure we only delete if we own the lock
        release_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        for client in self.clients:
            try:
                client.eval(release_script, 1, resource, lock_id)
            except redis.RedisError:
                continue  # Best effort release


@dataclass
class _LockContext:
    """Context manager for distributed lock."""
    
    lock: DistributedLock
    resource: str
    lock_id: str
    timeout_ms: int
    
    def __enter__(self) -> "_LockContext":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.lock._release_lock(self.resource, self.lock_id)
