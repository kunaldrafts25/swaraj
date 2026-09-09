r"""
SWARAJ Filesystem Jail - Strict path validation and access control.

SECURITY BOUNDARIES:
- Rejects ../ and ..\ traversal attempts
- Rejects absolute paths outside workspace
- Rejects symlink escapes
- Resolves canonical paths before authorization
- Validates BEFORE any file access occurs
"""

import os
from pathlib import Path
from typing import Optional


class FilesystemJailError(Exception):
    """Raised when filesystem jail violation detected."""
    pass


class FilesystemJail:
    """
    Enforces strict filesystem access controls.
    
    SECURITY BOUNDARIES:
    - All paths must be within configured workspace
    - Traversal attempts rejected before access
    - Symlink escapes detected and rejected
    - Canonical path resolution before validation
    """
    
    def __init__(self, workspace_root: Path | str):
        """
        Initialize filesystem jail.
        
        Args:
            workspace_root: Root directory for allowed file access
        """
        self.workspace_root = Path(workspace_root).resolve()
        
        # Ensure workspace exists
        if not self.workspace_root.exists():
            raise FileNotFoundError(f"Workspace root does not exist: {self.workspace_root}")
    
    def _contains_traversal(self, path_str: str) -> bool:
        """Check if path string contains traversal patterns."""
        # Check for common traversal patterns
        traversal_patterns = [
            '..',
            '..\\',
            '../',
        ]
        
        path_lower = path_str.lower()
        for pattern in traversal_patterns:
            if pattern in path_lower:
                return True
        
        return False
    
    def _is_absolute_path(self, path_str: str) -> bool:
        """Check if path is absolute."""
        return os.path.isabs(path_str)
    
    def resolve_safe_path(self, requested_path: str | Path) -> Path:
        """Resolve path and validate it is safely jailed within workspace."""
        path_str = str(requested_path).replace("\\", "/")
        # Strip leading workspace_root if already prepended
        ws_str = str(self.workspace_root).replace("\\", "/")
        if path_str.startswith(ws_str):
            path_str = path_str[len(ws_str):].lstrip("/")
        return self._resolve_and_validate(path_str)

    def _resolve_and_validate(self, requested_path: str) -> Path:
        """
        Resolve path and validate it's within workspace.
        
        SECURITY BOUNDARY: This is called BEFORE any file access.
        
        Args:
            requested_path: User-requested path (relative to workspace)
        
        Returns:
            Resolved Path within workspace
        
        Raises:
            FilesystemJailError: If path violates jail constraints
        """
        # Check for traversal patterns in original string
        if self._contains_traversal(requested_path):
            raise FilesystemJailError(
                f"Path traversal detected: {requested_path}"
            )
        
        # Check for absolute paths
        if self._is_absolute_path(requested_path):
            raise FilesystemJailError(
                f"Absolute paths not allowed: {requested_path}"
            )
        
        # Construct full path
        full_path = self.workspace_root / requested_path
        
        # Resolve to canonical path (resolves symlinks, normalizes)
        try:
            # First check if path exists
            if full_path.exists():
                canonical_path = full_path.resolve()
            else:
                # For non-existent paths, resolve parent and reconstruct
                # This allows writing to new files within workspace
                parent = full_path.parent
                if parent.exists():
                    canonical_parent = parent.resolve()
                    canonical_path = canonical_parent / full_path.name
                else:
                    # Try to resolve as much as possible
                    canonical_path = full_path.resolve()
        except (OSError, ValueError) as e:
            raise FilesystemJailError(
                f"Cannot resolve path: {requested_path} ({e})"
            )
        
        # Verify canonical path is within workspace
        try:
            canonical_path.relative_to(self.workspace_root)
        except ValueError:
            raise FilesystemJailError(
                f"Path escape detected: {requested_path} resolves to {canonical_path} "
                f"which is outside workspace {self.workspace_root}"
            )
        
        # Check for symlink escapes
        if canonical_path.exists():
            # Walk up the path checking each component for symlink escapes
            current = canonical_path
            while current != self.workspace_root:
                if current.is_symlink():
                    # Resolve the symlink and check if target is within workspace
                    try:
                        link_target = current.resolve()
                        link_target.relative_to(self.workspace_root)
                    except ValueError:
                        raise FilesystemJailError(
                            f"Symlink escape detected: {requested_path} "
                            f"contains symlink {current} pointing to {link_target} "
                            f"which is outside workspace"
                        )
                current = current.parent
        
        return canonical_path
    
    def validate_path(self, requested_path: str) -> Path:
        """
        Validate a path and return canonical path if safe.
        
        SECURITY BOUNDARY: Call this BEFORE any file access operation.
        
        Args:
            requested_path: Path relative to workspace root
        
        Returns:
            Canonical Path object
        
        Raises:
            FilesystemJailError: If path violates any jail constraint
        """
        return self._resolve_and_validate(requested_path)
    
    def safe_read(self, requested_path: str) -> bytes:
        """
        Safely read a file within the jail.
        
        Args:
            requested_path: Path relative to workspace root
        
        Returns:
            File contents as bytes
        
        Raises:
            FilesystemJailError: If path validation fails
            FileNotFoundError: If file doesn't exist
        """
        canonical_path = self.validate_path(requested_path)
        
        if not canonical_path.is_file():
            raise FileNotFoundError(f"Not a file: {requested_path}")
        
        return canonical_path.read_bytes()
    
    def safe_write(self, requested_path: str, data: bytes) -> Path:
        """
        Safely write to a file within the jail.
        
        Args:
            requested_path: Path relative to workspace root
            data: Bytes to write
        
        Returns:
            Canonical Path of written file
        
        Raises:
            FilesystemJailError: If path validation fails
        """
        canonical_path = self.validate_path(requested_path)
        
        # Ensure parent directory exists
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        
        canonical_path.write_bytes(data)
        return canonical_path
    
    def safe_list_dir(self, requested_path: str = ".") -> list[str]:
        """
        Safely list directory contents within the jail.
        
        Args:
            requested_path: Path relative to workspace root
        
        Returns:
            List of filenames in directory
        
        Raises:
            FilesystemJailError: If path validation fails
            NotADirectoryError: If path is not a directory
        """
        canonical_path = self.validate_path(requested_path)
        
        if not canonical_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {requested_path}")
        
        return [p.name for p in canonical_path.iterdir()]
