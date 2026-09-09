"""
Distributed Task Queue using Redis.

Provides background job processing for:
- Long-running agent workflows
- Batch document ingestion
- Asynchronous certificate generation
"""

import json
import time
import uuid
from typing import Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a queued task."""
    
    id: str
    type: str  # e.g., "agent_run", "document_ingest"
    payload: dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    node_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> "Task":
        d = json.loads(data)
        d["status"] = TaskStatus(d["status"])
        return cls(**d)


@dataclass
class TaskQueue:
    """
    Distributed task queue using Redis lists and pub/sub.
    
    Usage:
        queue = TaskQueue(redis_hosts=["redis1", "redis2"])
        
        # Enqueue task
        task_id = queue.enqueue("agent_run", {"task_description": "..."})
        
        # Dequeue and process (worker)
        task = queue.dequeue("agent_run")
        if task:
            result = process_task(task)
            queue.complete(task.id, result)
    """
    
    redis_hosts: list[str]
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    queue_prefix: str = "swaraj:queue"
    
    def __post_init__(self):
        if not REDIS_AVAILABLE:
            raise ImportError(
                "Redis package required for task queue. "
                "Install with: pip install redis"
            )
        
        # Use first available Redis host (could be extended to use cluster)
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
                self.client.ping()  # Test connection
                break
            except redis.RedisError:
                continue
        
        if self.client is None:
            raise ConnectionError("No Redis hosts available")
    
    def enqueue(self, task_type: str, payload: dict[str, Any], priority: int = 0) -> str:
        """
        Add task to queue.
        
        Args:
            task_type: Type of task (determines queue name)
            payload: Task parameters
            priority: Higher = more urgent (default 0)
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            type=task_type,
            payload=payload,
        )
        
        queue_key = f"{self.queue_prefix}:{task_type}"
        # Push to head for high priority, tail for normal
        if priority > 0:
            self.client.lpush(queue_key, task.to_json())
        else:
            self.client.rpush(queue_key, task.to_json())
        
        # Notify workers
        self.client.publish(f"{self.queue_prefix}:notifications", task_type)
        
        return task_id
    
    def dequeue(self, task_type: str, timeout_ms: int = 5000) -> Optional[Task]:
        """
        Get next task from queue (blocking).
        
        Args:
            task_type: Type of task to dequeue
            timeout_ms: Max time to wait (0 = no wait)
            
        Returns:
            Task or None if timeout
        """
        queue_key = f"{self.queue_prefix}:{task_type}"
        
        # BLPOP with timeout
        result = self.client.blpop(queue_key, timeout=timeout_ms / 1000.0)
        
        if result is None:
            return None
        
        _, task_json = result
        task = Task.from_json(task_json.decode("utf-8"))
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        
        # Store running task metadata
        self.client.setex(
            f"{self.queue_prefix}:running:{task.id}",
            3600,  # 1 hour TTL
            json.dumps({
                "node_id": self._get_node_id(),
                "started_at": task.started_at,
            })
        )
        
        return task
    
    def complete(self, task_id: str, result: dict[str, Any]) -> None:
        """Mark task as completed."""
        task_key = f"{self.queue_prefix}:task:{task_id}"
        
        task_data = self.client.get(task_key)
        if task_data:
            task = Task.from_json(task_data.decode("utf-8"))
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result
            
            self.client.setex(task_key, 86400, task.to_json())  # Keep 24h
        
        # Clean up running metadata
        self.client.delete(f"{self.queue_prefix}:running:{task_id}")
    
    def fail(self, task_id: str, error: str) -> None:
        """Mark task as failed."""
        task_key = f"{self.queue_prefix}:task:{task_id}"
        
        task_data = self.client.get(task_key)
        if task_data:
            task = Task.from_json(task_data.decode("utf-8"))
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
            task.error = error
            
            self.client.setex(task_key, 86400, task.to_json())
        
        self.client.delete(f"{self.queue_prefix}:running:{task_id}")
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        task_key = f"{self.queue_prefix}:task:{task_id}"
        task_data = self.client.get(task_key)
        
        if task_data:
            return Task.from_json(task_data.decode("utf-8"))
        return None
    
    def get_queue_length(self, task_type: str) -> int:
        """Get number of pending tasks."""
        queue_key = f"{self.queue_prefix}:{task_type}"
        return self.client.llen(queue_key)
    
    def _get_node_id(self) -> str:
        """Get unique identifier for this node."""
        import socket
        return f"{socket.gethostname()}-{uuid.getnode()}"
