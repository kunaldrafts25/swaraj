"""
Cluster Health Monitoring and Consensus.

Provides:
- Node health checks
- Leader election (simple)
- Cluster membership
- Consensus-based decisions
"""

import time
import socket
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class NodeStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


@dataclass
class NodeInfo:
    """Information about a cluster node."""
    
    node_id: str
    host: str
    port: int
    status: NodeStatus = NodeStatus.OFFLINE
    last_heartbeat: float = 0.0
    version: str = "2.0.0"
    capabilities: list[str] = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = ["agent_run", "document_ingest", "certificate_sign"]
        if self.last_heartbeat == 0.0:
            self.last_heartbeat = time.time()
    
    def to_json(self) -> str:
        import json
        d = asdict(self)
        d["status"] = self.status.value
        return json.dumps(d)
    
    @classmethod
    def from_json(cls, data: str) -> "NodeInfo":
        import json
        d = json.loads(data)
        d["status"] = NodeStatus(d["status"])
        return cls(**d)
    
    def is_alive(self, timeout_sec: float = 30.0) -> bool:
        """Check if node is considered alive based on heartbeat."""
        return (time.time() - self.last_heartbeat) < timeout_sec


@dataclass
class ClusterHealth:
    """
    Cluster health monitoring using Redis for coordination.
    
    Usage:
        health = ClusterHealth(
            redis_hosts=["redis1", "redis2"],
            node_id="node-1",
            host="192.168.1.10",
            port=8000
        )
        
        # Register this node
        health.register()
        
        # Check overall cluster health
        status = health.get_cluster_status()
        if status.quorum_met:
            # Safe to proceed with distributed operations
            pass
    """
    
    redis_hosts: list[str]
    node_id: str
    host: str
    port: int
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    heartbeat_interval_sec: float = 5.0
    node_timeout_sec: float = 30.0
    
    def __post_init__(self):
        if not REDIS_AVAILABLE:
            raise ImportError(
                "Redis package required for cluster health. "
                "Install with: pip install redis"
            )
        
        self.client = None
        for host in self.redis_hosts:
            try:
                self.client = redis.Redis(
                    host=host,
                    port=self.redis_port,
                    db=self.redis_db,
                    password=self.redis_password,
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0,
                )
                self.client.ping()
                break
            except redis.RedisError:
                continue
        
        if self.client is None:
            raise ConnectionError("No Redis hosts available")
        
        self.key_prefix = "swaraj:cluster"
        self.info = NodeInfo(
            node_id=self.node_id,
            host=self.host,
            port=self.port,
        )
    
    def register(self) -> None:
        """Register this node in the cluster."""
        self.info.status = NodeStatus.HEALTHY
        self._heartbeat()
    
    def deregister(self) -> None:
        """Remove this node from cluster (graceful shutdown)."""
        key = f"{self.key_prefix}:nodes:{self.node_id}"
        self.client.delete(key)
    
    def _heartbeat(self) -> None:
        """Send heartbeat update."""
        key = f"{self.key_prefix}:nodes:{self.node_id}"
        self.info.last_heartbeat = time.time()
        self.client.setex(key, int(self.node_timeout_sec * 2), self.info.to_json())
    
    def send_heartbeats(self) -> None:
        """Continuous heartbeat loop (run in background thread)."""
        while True:
            try:
                self._heartbeat()
            except redis.RedisError:
                self.info.status = NodeStatus.DEGRADED
            time.sleep(self.heartbeat_interval_sec)
    
    def get_all_nodes(self) -> list[NodeInfo]:
        """Get all registered nodes."""
        pattern = f"{self.key_prefix}:nodes:*"
        nodes = []
        
        for key in self.client.keys(pattern):
            data = self.client.get(key)
            if data:
                try:
                    node = NodeInfo.from_json(data.decode("utf-8"))
                    # Update status based on heartbeat
                    if not node.is_alive(self.node_timeout_sec):
                        node.status = NodeStatus.OFFLINE
                    nodes.append(node)
                except Exception:
                    continue
        
        return nodes
    
    def get_healthy_nodes(self) -> list[NodeInfo]:
        """Get only healthy nodes."""
        nodes = self.get_all_nodes()
        return [n for n in nodes if n.status == NodeStatus.HEALTHY and n.is_alive()]
    
    def get_cluster_status(self) -> "ClusterStatus":
        """
        Get overall cluster health status.
        
        Returns quorum information for consensus decisions.
        """
        nodes = self.get_all_nodes()
        healthy = [n for n in nodes if n.status == NodeStatus.HEALTHY and n.is_alive()]
        
        total = len(nodes)
        healthy_count = len(healthy)
        
        # Quorum = majority
        quorum = (total // 2) + 1 if total > 0 else 1
        quorum_met = healthy_count >= quorum
        
        return ClusterStatus(
            total_nodes=total,
            healthy_nodes=healthy_count,
            quorum_required=quorum,
            quorum_met=quorum_met,
            can_operate=quorum_met,
        )
    
    def elect_leader(self, resource: str) -> bool:
        """
        Simple leader election using Redis SET NX.
        
        Returns True if this node became the leader.
        """
        key = f"{self.key_prefix}:leader:{resource}"
        leader_key = f"leader:{self.node_id}"
        
        # Try to become leader (5 minute term)
        result = self.client.set(key, leader_key, nx=True, ex=300)
        return result is not None
    
    def get_leader(self, resource: str) -> Optional[str]:
        """Get current leader for a resource."""
        key = f"{self.key_prefix}:leader:{resource}"
        leader = self.client.get(key)
        
        if leader:
            return leader.decode("utf-8").replace("leader:", "")
        return None


@dataclass
class ClusterStatus:
    """Overall cluster health status."""
    
    total_nodes: int
    healthy_nodes: int
    quorum_required: int
    quorum_met: bool
    can_operate: bool
