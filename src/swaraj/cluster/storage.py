"""
Shared Artifact Storage abstraction for multi-node operation.

Supports multiple backends:
- Local filesystem (single-node)
- MinIO/S3 (multi-node)
- NFS mount (shared storage)
"""

import os
import hashlib
from pathlib import Path
from typing import Optional, BinaryIO
from abc import ABC, abstractmethod


class StorageError(Exception):
    """Raised when storage operation fails."""
    pass


class ArtifactStorageBackend(ABC):
    """Abstract base class for artifact storage."""
    
    @abstractmethod
    def store(self, key: str, data: bytes, metadata: dict) -> str:
        """Store artifact, return URI."""
        pass
    
    @abstractmethod
    def retrieve(self, key: str) -> bytes:
        """Retrieve artifact by key."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if artifact exists."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete artifact."""
        pass


class LocalFilesystemStorage(ArtifactStorageBackend):
    """
    Local filesystem storage (single-node only).
    
    WARNING: Not suitable for multi-node clusters.
    Use MinIOStorage for distributed operation.
    """
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def store(self, key: str, data: bytes, metadata: dict) -> str:
        path = self.base_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        
        # Store metadata alongside
        meta_path = path.with_suffix(path.suffix + ".meta")
        import json
        meta_path.write_text(json.dumps(metadata))
        
        return f"file://{path}"
    
    def retrieve(self, key: str) -> bytes:
        path = self.base_path / key
        if not path.exists():
            raise StorageError(f"Artifact not found: {key}")
        return path.read_bytes()
    
    def exists(self, key: str) -> bool:
        return (self.base_path / key).exists()
    
    def delete(self, key: str) -> None:
        path = self.base_path / key
        if path.exists():
            path.unlink()


class MinIOStorage(ArtifactStorageBackend):
    """
    MinIO/S3-compatible storage for multi-node clusters.
    
    Usage:
        storage = MinIOStorage(
            endpoint="minio.internal:9000",
            access_key="...",
            secret_key="...",
            bucket="swaraj-artifacts"
        )
    """
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ):
        try:
            from minio import Minio
        except ImportError:
            raise ImportError(
                "MinIO package required. Install with: pip install minio"
            )
        
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self.bucket = bucket
        
        # Ensure bucket exists
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)
    
    def store(self, key: str, data: bytes, metadata: dict) -> str:
        import io
        
        # Add checksum to metadata
        metadata["sha256"] = hashlib.sha256(data).hexdigest()
        metadata["size"] = len(data)
        
        # Convert metadata to HTTP headers
        headers = {f"x-amz-meta-{k}": str(v) for k, v in metadata.items()}
        
        self.client.put_object(
            self.bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            metadata=headers,
        )
        
        return f"s3://{self.bucket}/{key}"
    
    def retrieve(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        return response.read()
    
    def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> None:
        self.client.remove_object(self.bucket, key)


def create_storage(config: dict) -> ArtifactStorageBackend:
    """
    Factory function to create appropriate storage backend.
    
    Config examples:
        {"type": "local", "base_path": "/data/artifacts"}
        {"type": "minio", "endpoint": "...", "access_key": "...", ...}
    """
    storage_type = config.get("type", "local")
    
    if storage_type == "local":
        return LocalFilesystemStorage(config["base_path"])
    elif storage_type == "minio":
        return MinIOStorage(
            endpoint=config["endpoint"],
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            bucket=config["bucket"],
            secure=config.get("secure", False),
        )
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
