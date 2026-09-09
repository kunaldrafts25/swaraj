"""Tests for registry checksum verification and fail-closed behavior.

REQ-173: Model SHA256 Verification
REQ-174: Fail-Closed on Mismatch
REQ-175: Reject Placeholder/fabricated checksums
REQ-183: Filesystem Jail Requirements

These tests use temporary fixture files and do NOT require the real GGUF artifact.
"""

import hashlib
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest
import yaml

from swaraj.registry.loader import (
    RegistryLoader,
    ChecksumMismatchError,
    ModelNotFoundError,
    ManifestValidationError,
    PathTraversalError,
)
from swaraj.registry.manifest_schema import ModelManifest, ChecksumStatus


def create_test_manifest(
    tmp_path: Path,
    name: str = "test-model",
    gguf_filename: str = "test.gguf",
    sha256: str = "a" * 64,
    signature: str = "test-signature",
) -> tuple[Path, Path]:
    """Create a test manifest and optional artifact.
    
    Returns:
        Tuple of (manifest_dir, models_dir)
    """
    manifest_dir = tmp_path / "manifests"
    models_dir = tmp_path / "models"
    manifest_dir.mkdir(exist_ok=True)
    models_dir.mkdir(exist_ok=True)
    
    manifest_data = {
        "name": name,
        "version": "1.0.0",
        "gguf_path": gguf_filename,
        "sha256": sha256,
        "quant": "Q4_K_M",
        "context_length": 8192,
        "hardware_tier_min": "cpu_only",
        "capability_vector": None,
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "signature": signature,
    }
    
    manifest_path = manifest_dir / f"{name}.yaml"
    with open(manifest_path, "w") as f:
        yaml.dump(manifest_data, f)
    
    return manifest_dir, models_dir


def create_test_artifact(models_dir: Path, filename: str, content: bytes = b"test content") -> Path:
    """Create a test artifact file."""
    artifact_path = models_dir / filename
    artifact_path.write_bytes(content)
    return artifact_path


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest().lower()


class TestChecksumVerification:
    """Test checksum verification logic."""
    
    def test_valid_checksum_passes(self, tmp_path: Path):
        """Verify that a valid checksum passes verification."""
        manifest_dir, models_dir = create_test_manifest(tmp_path)
        
        # Create artifact with known content
        artifact_path = create_test_artifact(models_dir, "test.gguf")
        actual_sha256 = calculate_sha256(artifact_path)
        
        # Update manifest with correct checksum
        _, _ = create_test_manifest(tmp_path, sha256=actual_sha256)
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        manifest = loader.load_manifest("test-model")
        status = loader.verify_model(manifest)
        
        assert status == ChecksumStatus.VERIFIED
    
    def test_invalid_checksum_fails(self, tmp_path: Path):
        """Verify that an invalid checksum fails verification."""
        manifest_dir, models_dir = create_test_manifest(
            tmp_path,
            sha256="b" * 64,  # Wrong checksum
        )
        
        # Create artifact
        create_test_artifact(models_dir, "test.gguf")
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        manifest = loader.load_manifest("test-model")
        status = loader.verify_model(manifest)
        
        assert status == ChecksumStatus.MISMATCH
    
    def test_load_verified_model_rejects_mismatch(self, tmp_path: Path):
        """Verify that load_verified_model raises on checksum mismatch."""
        manifest_dir, models_dir = create_test_manifest(
            tmp_path,
            sha256="b" * 64,  # Wrong checksum
        )
        
        # Create artifact
        create_test_artifact(models_dir, "test.gguf")
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        
        with pytest.raises(ChecksumMismatchError) as exc_info:
            loader.load_verified_model("test-model")
        
        assert exc_info.value.reason == "checksum_mismatch"
        assert exc_info.value.expected == "b" * 64


class TestFailClosedBehavior:
    """Test fail-closed behavior for various failure modes."""
    
    def test_missing_artifact_fails(self, tmp_path: Path):
        """Verify that missing artifact triggers fail-closed."""
        manifest_dir, models_dir = create_test_manifest(tmp_path)
        
        # Do NOT create the artifact
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        manifest = loader.load_manifest("test-model")
        status = loader.verify_model(manifest)
        
        assert status == ChecksumStatus.MISSING
    
    def test_load_verified_model_rejects_missing_artifact(self, tmp_path: Path):
        """Verify that load_verified_model raises on missing artifact."""
        manifest_dir, models_dir = create_test_manifest(tmp_path)
        
        # Do NOT create the artifact
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        
        with pytest.raises(ModelNotFoundError) as exc_info:
            loader.load_verified_model("test-model")
        
        assert exc_info.value.reason == "model_not_found"
        assert "test.gguf" in exc_info.value.path
    
    def test_missing_checksum_fails(self, tmp_path: Path):
        """Verify that manifest with missing checksum field fails validation."""
        manifest_dir = tmp_path / "manifests"
        models_dir = tmp_path / "models"
        manifest_dir.mkdir()
        models_dir.mkdir()
        
        # Create manifest without sha256 field
        manifest_data = {
            "name": "test-model",
            "version": "1.0.0",
            "gguf_path": "test.gguf",
            # Missing sha256
            "quant": "Q4_K_M",
            "context_length": 8192,
            "hardware_tier_min": "cpu_only",
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "signature": "test-sig",
        }
        
        manifest_path = manifest_dir / "test-model.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f)
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        
        with pytest.raises(ManifestValidationError):
            loader.load_manifest("test-model")
    
    def test_placeholder_checksum_fails(self, tmp_path: Path):
        """Verify that placeholder checksum is rejected."""
        manifest_dir, models_dir = create_test_manifest(
            tmp_path,
            sha256="0" * 64,  # Placeholder pattern
        )
        
        # Create artifact (even though it won't match)
        create_test_artifact(models_dir, "test.gguf")
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        manifest = loader.load_manifest("test-model")
        status = loader.verify_model(manifest)
        
        assert status == ChecksumStatus.PLACEHOLDER
    
    def test_load_verified_model_rejects_placeholder_checksum(self, tmp_path: Path):
        """Verify that load_verified_model raises on placeholder checksum."""
        manifest_dir, models_dir = create_test_manifest(
            tmp_path,
            sha256="f" * 64,  # Another placeholder pattern
        )
        
        create_test_artifact(models_dir, "test.gguf")
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        
        with pytest.raises(ChecksumMismatchError) as exc_info:
            loader.load_verified_model("test-model")
        
        assert exc_info.value.reason == "checksum_mismatch"


class TestPathTraversal:
    """Test filesystem jail path traversal rejection."""
    
    def test_dotdot_traversal_rejected(self, tmp_path: Path):
        """Verify that ../ traversal is rejected."""
        manifest_dir = tmp_path / "manifests"
        models_dir = tmp_path / "models"
        manifest_dir.mkdir(exist_ok=True)
        models_dir.mkdir(exist_ok=True)
        
        # Create manifest with path traversal
        manifest_data = {
            "name": "evil-model",
            "version": "1.0.0",
            "gguf_path": "../../../etc/passwd",
            "sha256": "a" * 64,
            "quant": "Q4_K_M",
            "context_length": 8192,
            "hardware_tier_min": "cpu_only",
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "signature": "test-sig",
        }
        
        manifest_path = manifest_dir / "evil-model.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f)
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        manifest = loader.load_manifest("evil-model")
        
        with pytest.raises(PathTraversalError) as exc_info:
            loader.verify_model(manifest)
        
        assert exc_info.value.reason == "path_traversal"
        assert "../../../etc/passwd" in exc_info.value.path
    
    def test_backslash_traversal_rejected(self, tmp_path: Path):
        """Verify that ..\\ traversal is rejected."""
        manifest_dir = tmp_path / "manifests"
        models_dir = tmp_path / "models"
        manifest_dir.mkdir(exist_ok=True)
        models_dir.mkdir(exist_ok=True)
        
        manifest_data = {
            "name": "evil-model",
            "version": "1.0.0",
            "gguf_path": "..\\..\\secret.gguf",
            "sha256": "a" * 64,
            "quant": "Q4_K_M",
            "context_length": 8192,
            "hardware_tier_min": "cpu_only",
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "signature": "test-sig",
        }
        
        manifest_path = manifest_dir / "evil-model.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f)
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        manifest = loader.load_manifest("evil-model")
        
        with pytest.raises(PathTraversalError):
            loader.verify_model(manifest)
    
    def test_absolute_path_rejected(self, tmp_path: Path):
        """Verify that absolute paths are rejected."""
        manifest_dir = tmp_path / "manifests"
        models_dir = tmp_path / "models"
        manifest_dir.mkdir(exist_ok=True)
        models_dir.mkdir(exist_ok=True)
        
        manifest_data = {
            "name": "evil-model",
            "version": "1.0.0",
            "gguf_path": "/etc/shadow",
            "sha256": "a" * 64,
            "quant": "Q4_K_M",
            "context_length": 8192,
            "hardware_tier_min": "cpu_only",
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "signature": "test-sig",
        }
        
        manifest_path = manifest_dir / "evil-model.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f)
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        manifest = loader.load_manifest("evil-model")
        
        with pytest.raises(PathTraversalError):
            loader.verify_model(manifest)
    
    def test_symlink_escape_attempt_rejected(self, tmp_path: Path):
        """Verify that symlink-based escape attempts are handled."""
        manifest_dir = tmp_path / "manifests"
        models_dir = tmp_path / "models"
        outside_dir = tmp_path / "outside"
        manifest_dir.mkdir()
        models_dir.mkdir()
        outside_dir.mkdir()
        
        # Create a file outside models_dir
        secret_file = outside_dir / "secret.gguf"
        secret_file.write_bytes(b"secret content")
        
        # Create symlink inside models_dir pointing outside
        symlink_path = models_dir / "escape.gguf"
        try:
            symlink_path.symlink_to(secret_file)
        except OSError as e:
            pytest.skip(f"Symlinks not permitted in current environment: {e}")
        
        manifest_data = {
            "name": "escape-model",
            "version": "1.0.0",
            "gguf_path": "escape.gguf",
            "sha256": "a" * 64,
            "quant": "Q4_K_M",
            "context_length": 8192,
            "hardware_tier_min": "cpu_only",
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "signature": "test-sig",
        }
        
        manifest_path = manifest_dir / "escape-model.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f)
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        manifest = loader.load_manifest("escape-model")
        
        # The path resolution should detect the escape
        with pytest.raises(PathTraversalError):
            loader.verify_model(manifest)


class TestRegistryStatus:
    """Test registry status reporting."""
    
    def test_registry_not_ready_without_verified_models(self, tmp_path: Path):
        """Verify registry reports not ready when no models are verified."""
        manifest_dir, models_dir = create_test_manifest(
            tmp_path,
            sha256="b" * 64,  # Wrong checksum
        )
        
        create_test_artifact(models_dir, "test.gguf")
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        status = loader.get_registry_status()
        
        assert status["ready"] is False
        assert status["verified_models"] == 0
    
    def test_registry_ready_with_verified_model(self, tmp_path: Path):
        """Verify registry reports ready when model is verified."""
        manifest_dir, models_dir = create_test_manifest(tmp_path)
        
        artifact_path = create_test_artifact(models_dir, "test.gguf")
        actual_sha256 = calculate_sha256(artifact_path)
        
        # Recreate manifest with correct checksum
        create_test_manifest(tmp_path, sha256=actual_sha256)
        
        loader = RegistryLoader(registry_dir=manifest_dir, models_dir=models_dir)
        
        # Load and verify the model
        loader.load_verified_model("test-model")
        
        status = loader.get_registry_status()
        
        assert status["ready"] is True
        assert status["verified_models"] >= 1


class TestManifestSchema:
    """Test manifest schema validation."""
    
    def test_placeholder_detection_all_zeros(self):
        """Verify detection of all-zeros placeholder."""
        from swaraj.registry.manifest_schema import ModelManifest, HardwareTier
        from datetime import datetime, timezone
        
        manifest = ModelManifest(
            name="test-model",
            version="1.0.0",
            gguf_path="test.gguf",
            sha256="0" * 64,
            quant="Q4_K_M",
            context_length=8192,
            hardware_tier_min=HardwareTier.CPU_ONLY,
            signed_at=datetime.now(timezone.utc),
            signature="sig",
        )
        
        assert manifest.is_checksum_placeholder() is True
    
    def test_placeholder_detection_all_f(self):
        """Verify detection of all-f placeholder."""
        from swaraj.registry.manifest_schema import ModelManifest, HardwareTier
        from datetime import datetime, timezone
        
        manifest = ModelManifest(
            name="test-model",
            version="1.0.0",
            gguf_path="test.gguf",
            sha256="f" * 64,
            quant="Q4_K_M",
            context_length=8192,
            hardware_tier_min=HardwareTier.CPU_ONLY,
            signed_at=datetime.now(timezone.utc),
            signature="sig",
        )
        
        assert manifest.is_checksum_placeholder() is True
    
    def test_valid_checksum_not_placeholder(self):
        """Verify that real-looking checksums are not flagged as placeholders."""
        from swaraj.registry.manifest_schema import ModelManifest, HardwareTier
        from datetime import datetime, timezone
        
        # A realistic-looking SHA256
        real_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        
        manifest = ModelManifest(
            name="test-model",
            version="1.0.0",
            gguf_path="test.gguf",
            sha256=real_sha,
            quant="Q4_K_M",
            context_length=8192,
            hardware_tier_min=HardwareTier.CPU_ONLY,
            signed_at=datetime.now(timezone.utc),
            signature="sig",
        )
        
        assert manifest.is_checksum_placeholder() is False
