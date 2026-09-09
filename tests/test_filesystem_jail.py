"""Tests for SWARAJ Filesystem Jail - Path validation and access control."""

import os
import pytest
from pathlib import Path

from swaraj.tools.fs_jail import FilesystemJail, FilesystemJailError


@pytest.fixture
def workspace_root(tmp_path):
    """Create temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    # Create some test files
    (workspace / "test.txt").write_text("test content")
    (workspace / "subdir").mkdir()
    (workspace / "subdir" / "nested.txt").write_text("nested content")
    
    return workspace


@pytest.fixture
def jail(workspace_root):
    """Create FilesystemJail instance."""
    return FilesystemJail(workspace_root)


class TestTraversalRejection:
    """Test path traversal rejection."""
    
    def test_dotdot_slash_rejected(self, jail):
        """../ traversal is rejected."""
        with pytest.raises(FilesystemJailError) as exc_info:
            jail.validate_path("../secret")
        
        assert "traversal" in str(exc_info.value).lower()
    
    def test_dotdot_backslash_rejected(self, jail):
        """..\ traversal is rejected."""
        with pytest.raises(FilesystemJailError) as exc_info:
            jail.validate_path("..\\secret")
        
        assert "traversal" in str(exc_info.value).lower()
    
    def test_complex_traversal_rejected(self, jail):
        """Complex traversal patterns are rejected."""
        with pytest.raises(FilesystemJailError):
            jail.validate_path("subdir/../../secret")
    
    def test_encoded_traversal_rejected(self, jail):
        """URL-encoded traversal is rejected."""
        with pytest.raises(FilesystemJailError):
            jail.validate_path(".../secret")


class TestAbsolutePathRejection:
    """Test absolute path rejection."""
    
    def test_unix_absolute_rejected(self, jail):
        """Unix absolute paths are rejected."""
        with pytest.raises(FilesystemJailError) as exc_info:
            jail.validate_path("/etc/passwd")
        
        assert "absolute" in str(exc_info.value).lower()
    
    def test_etc_passwd_rejected(self, jail):
        """/etc/passwd access is rejected."""
        with pytest.raises(FilesystemJailError):
            jail.validate_path("/etc/passwd")


class TestValidPaths:
    """Test valid path acceptance."""
    
    def test_simple_file_accepted(self, jail, workspace_root):
        """Simple relative file paths are accepted."""
        path = jail.validate_path("test.txt")
        
        assert path.exists()
        assert path.is_file()
        assert workspace_root in path.resolve().parents or path.resolve().startswith(str(workspace_root))
    
    def test_subdirectory_accepted(self, jail, workspace_root):
        """Subdirectory paths are accepted."""
        path = jail.validate_path("subdir/nested.txt")
        
        assert path.exists()
        assert path.is_file()
    
    def test_current_dir_accepted(self, jail):
        """Current directory (.) is accepted."""
        path = jail.validate_path(".")
        
        assert path.is_dir()


class TestSymlinkEscape:
    """Test symlink escape detection."""
    
    def test_symlink_to_outside_rejected(self, jail, workspace_root, tmp_path):
        """Symlinks pointing outside workspace are rejected."""
        # Create a file outside workspace
        outside_file = tmp_path / "outside_secret.txt"
        outside_file.write_text("secret")
        
        # Create symlink inside workspace pointing outside
        symlink_path = workspace_root / "evil_link"
        symlink_path.symlink_to(outside_file)
        
        with pytest.raises(FilesystemJailError) as exc_info:
            jail.validate_path("evil_link")
        
        assert "symlink" in str(exc_info.value).lower() or "escape" in str(exc_info.value).lower()


class TestSafeOperations:
    """Test safe read/write operations."""
    
    def test_safe_read(self, jail):
        """safe_read returns file contents."""
        content = jail.safe_read("test.txt")
        
        assert content == b"test content"
    
    def test_safe_write(self, jail):
        """safe_write creates file within workspace."""
        jail.safe_write("newfile.txt", b"new content")
        
        path = jail.validate_path("newfile.txt")
        assert path.exists()
        assert path.read_bytes() == b"new content"
    
    def test_safe_read_nonexistent_fails(self, jail):
        """safe_read raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            jail.safe_read("nonexistent.txt")
    
    def test_safe_list_dir(self, jail):
        """safe_list_dir returns directory contents."""
        contents = jail.safe_list_dir(".")
        
        assert "test.txt" in contents
        assert "subdir" in contents


class TestCanonicalPathResolution:
    """Test canonical path resolution."""
    
    def test_path_normalized(self, jail, workspace_root):
        """Paths are normalized to canonical form."""
        path = jail.validate_path("./test.txt")
        
        # Should resolve to clean path without ./
        assert "test.txt" in str(path)
    
    def test_resolve_before_validate(self, jail):
        """Path is resolved before validation."""
        # Valid path without traversal should work
        path = jail.validate_path("test.txt")
        assert path.exists()
        
        # Path that resolves within workspace but contains ../ should be rejected
        # because we check for traversal patterns BEFORE resolution
        import pytest
        with pytest.raises(Exception):  # FilesystemJailError
            jail.validate_path("subdir/../test.txt")
