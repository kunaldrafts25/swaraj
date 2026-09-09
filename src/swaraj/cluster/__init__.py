"""
SWARAJ v2 Cluster Module - Distributed Operation Support.

Provides primitives for multi-node operation:
- Distributed locking (RedLock)
- Shared worker queue (Redis-backed)
- Consensus health checks
- Shared artifact storage abstraction
"""

from swaraj.cluster.lock import DistributedLock, LockError
from swaraj.cluster.queue import TaskQueue, TaskStatus
from swaraj.cluster.storage import (
    LocalFilesystemStorage,
    MinIOStorage,
    create_storage,
    ArtifactStorageBackend,
    StorageError,
)
from swaraj.cluster.health import ClusterHealth, NodeStatus, NodeInfo, ClusterStatus

__all__ = [
    "DistributedLock",
    "LockError",
    "TaskQueue",
    "TaskStatus",
    "LocalFilesystemStorage",
    "MinIOStorage",
    "create_storage",
    "ArtifactStorageBackend",
    "StorageError",
    "ClusterHealth",
    "NodeStatus",
    "NodeInfo",
    "ClusterStatus",
]
