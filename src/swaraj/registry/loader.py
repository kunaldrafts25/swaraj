"""Registry loader for SWARAJ v2 model manifests.

Implements fail-closed model loading with strict checksum verification.
REQ-013: Registry Contract
REQ-173: Model SHA256 Verification
REQ-174: Fail-Closed on Mismatch
REQ-175: Reject Placeholder/fabricated checksums
REQ-183: Filesystem Jail Requirements
"""

import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List

import yaml

from swaraj.config import get_settings
from swaraj.registry.manifest_schema import (
    ModelManifest,
    ChecksumStatus,
    HardwareTier,
)


class RegistryError(Exception):
    """Base exception for registry operations."""
    
    def __init__(self, message: str, reason: str = "unknown"):
        super().__init__(message)
        self.reason = reason


class ChecksumMismatchError(RegistryError):
    """Raised when manifest checksum does not match artifact."""
    
    def __init__(self, expected: str, actual: Optional[str]):
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Checksum mismatch: expected {expected}, got {actual}",
            reason="checksum_mismatch",
        )


class ModelNotFoundError(RegistryError):
    """Raised when model artifact file is missing."""
    
    def __init__(self, path: str):
        self.path = path
        super().__init__(
            f"Model artifact not found: {path}",
            reason="model_not_found",
        )


class ManifestValidationError(RegistryError):
    """Raised when manifest fails schema validation."""
    
    def __init__(self, errors: List[Dict[str, Any]]):
        self.errors = errors
        error_str = "; ".join(str(e) for e in errors)
        super().__init__(
            f"Manifest validation failed: {error_str}",
            reason="manifest_validation",
        )


class PathTraversalError(RegistryError):
    """Raised when path traversal is detected in gguf_path."""
    
    def __init__(self, path: str):
        self.path = path
        super().__init__(
            f"Path traversal detected: {path}",
            reason="path_traversal",
        )


class RegistryLoader:
    """Load and validate model manifests from the registry.
    
    Implements fail-closed behavior:
    - Missing artifact → reject
    - Missing checksum → reject
    - Placeholder checksum → reject
    - Checksum mismatch → reject
    - Path traversal → reject
    
    Only loads models with verified integrity.
    """
    
    def __init__(self, registry_dir: Optional[Path] = None, models_dir: Optional[Path] = None):
        """Initialize registry loader.
        
        Args:
            registry_dir: Directory containing manifest YAML files.
            models_dir: Directory containing model artifacts.
        """
        settings = get_settings()
        self.registry_dir = registry_dir or settings.registry_dir
        self.models_dir = models_dir or settings.models_dir
        self._loaded_manifests: Dict[str, ModelManifest] = {}
        self._verification_status: Dict[str, ChecksumStatus] = {}
    
    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            Lowercase hexadecimal SHA256 string.
        
        Raises:
            FileNotFoundError: If file does not exist.
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest().lower()
    
    def _validate_path_safety(self, gguf_path: str) -> Path:
        """Validate that gguf_path does not contain path traversal.
        
        REQ-183: Filesystem Jail Requirements
        
        Args:
            gguf_path: Relative path from manifest.
        
        Returns:
            Safe resolved absolute path.
        
        Raises:
            PathTraversalError: If path traversal is detected.
        """
        # Check for obvious traversal patterns in the raw string
        dangerous_patterns = ["..", "~"]
        for pattern in dangerous_patterns:
            if pattern in gguf_path:
                raise PathTraversalError(gguf_path)
        
        # Also check for backslash-based traversal (Windows-style)
        if "\\" in gguf_path:
            # Split on backslash and check each component
            components = gguf_path.split("\\")
            for comp in components:
                if comp == ".." or comp.startswith("..") or comp.endswith(".."):
                    raise PathTraversalError(gguf_path)
        
        # Parse the path component by component
        path_obj = Path(gguf_path)
        
        # Reject absolute paths
        if path_obj.is_absolute():
            raise PathTraversalError(gguf_path)
        
        # Resolve the full path within models_dir
        resolved = (self.models_dir / path_obj).resolve()
        
        # Ensure resolved path is within models_dir
        models_resolved = self.models_dir.resolve()
        try:
            resolved.relative_to(models_resolved)
        except ValueError:
            raise PathTraversalError(gguf_path)
        
        return resolved
    
    def load_manifest(self, manifest_name: str) -> ModelManifest:
        """Load and validate a model manifest.
        
        Args:
            manifest_name: Name of the manifest (without .yaml extension).
        
        Returns:
            Validated ModelManifest object.
        
        Raises:
            ManifestValidationError: If manifest fails schema validation.
            FileNotFoundError: If manifest file does not exist.
        """
        manifest_path = self.registry_dir / f"{manifest_name}.yaml"
        
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f)
        
        if not isinstance(manifest_data, dict):
            raise ManifestValidationError([{"error": "Manifest must be a YAML mapping"}])
        
        try:
            manifest = ModelManifest(**manifest_data)
        except Exception as e:
            # Extract validation errors from Pydantic
            if hasattr(e, "errors"):
                errors = e.errors()
            else:
                errors = [{"error": str(e)}]
            raise ManifestValidationError(errors) from e
        
        return manifest
    
    def verify_model(self, manifest: ModelManifest) -> ChecksumStatus:
        """Verify model artifact against manifest checksum.
        
        Implements fail-closed verification:
        - Missing artifact → MISSING
        - Placeholder checksum → PLACEHOLDER
        - Mismatch → MISMATCH
        - Match → VERIFIED
        
        Args:
            manifest: Validated ModelManifest.
        
        Returns:
            ChecksumStatus indicating verification result.
        
        Raises:
            PathTraversalError: If path traversal is detected.
        """
        # Validate path safety first - this may raise PathTraversalError
        artifact_path = self._validate_path_safety(manifest.gguf_path)
        
        # Check if artifact exists
        if not artifact_path.exists():
            self._verification_status[manifest.name] = ChecksumStatus.MISSING
            return ChecksumStatus.MISSING
        
        # Check for placeholder checksum before calculating
        if manifest.is_checksum_placeholder():
            self._verification_status[manifest.name] = ChecksumStatus.PLACEHOLDER
            return ChecksumStatus.PLACEHOLDER
        
        # Calculate actual checksum
        try:
            actual_sha256 = self._calculate_sha256(artifact_path)
        except (IOError, OSError):
            self._verification_status[manifest.name] = ChecksumStatus.MISSING
            return ChecksumStatus.MISSING
        
        # Compare checksums
        status = manifest.get_checksum_status(actual_sha256)
        self._verification_status[manifest.name] = status
        return status
    
    def load_verified_model(self, manifest_name: str) -> ModelManifest:
        """Load and verify a model manifest with fail-closed behavior.
        
        This is the primary entry point for loading models.
        It will only return successfully if:
        - Manifest exists and validates
        - Artifact exists
        - Checksum is not a placeholder
        - Checksum matches
        
        Args:
            manifest_name: Name of the manifest (without .yaml extension).
        
        Returns:
            Verified ModelManifest.
        
        Raises:
            ManifestValidationError: If manifest fails validation.
            ModelNotFoundError: If artifact is missing.
            ChecksumMismatchError: If checksum is placeholder or mismatches.
            PathTraversalError: If path traversal is detected.
        """
        manifest = self.load_manifest(manifest_name)
        status = self.verify_model(manifest)
        
        if status == ChecksumStatus.MISSING:
            raise ModelNotFoundError(manifest.gguf_path)
        
        if status == ChecksumStatus.PLACEHOLDER:
            raise ChecksumMismatchError(
                expected=manifest.sha256,
                actual=None,
            )
        
        if status == ChecksumStatus.MISMATCH:
            # Try to calculate actual for better error message
            try:
                artifact_path = self._validate_path_safety(manifest.gguf_path)
                if artifact_path.exists():
                    actual = self._calculate_sha256(artifact_path)
                else:
                    actual = None
            except Exception:
                actual = None
            
            raise ChecksumMismatchError(
                expected=manifest.sha256,
                actual=actual,
            )
        
        # Status is VERIFIED
        self._loaded_manifests[manifest.name] = manifest
        return manifest
    
    def list_manifests(self) -> List[str]:
        """List all available manifest names.
        
        Returns:
            List of manifest names (without .yaml extension).
        """
        # Handle SwarajSettings object or Path
        if hasattr(self.registry_dir, 'model_dump'):
            # It's a SwarajSettings object, get the registry_dir field
            registry_path = Path(self.registry_dir.registry_dir)
        elif isinstance(self.registry_dir, str):
            registry_path = Path(self.registry_dir)
        else:
            registry_path = self.registry_dir
        
        if not registry_path.exists():
            return []
        
        manifests = []
        for f in registry_path.glob("*.yaml"):
            manifests.append(f.stem)
        
        return sorted(manifests)
    
    def get_verification_status(self, manifest_name: str) -> Optional[ChecksumStatus]:
        """Get verification status for a loaded manifest.
        
        Args:
            manifest_name: Name of the manifest.
        
        Returns:
            ChecksumStatus if known, None otherwise.
        """
        return self._verification_status.get(manifest_name)
    
    def get_loaded_manifest(self, name: str) -> Optional[ModelManifest]:
        """Get a previously loaded and verified manifest.
        
        Args:
            name: Manifest name.
        
        Returns:
            ModelManifest if loaded and verified, None otherwise.
        """
        return self._loaded_manifests.get(name)
    
    def is_registry_ready(self) -> bool:
        """Check if registry has at least one verified model.
        
        Returns:
            True if at least one model is verified and loaded.
        """
        return len(self._loaded_manifests) > 0
    
    def get_registry_status(self) -> Dict[str, Any]:
        """Get comprehensive registry status for health checks.
        
        Returns:
            Dictionary with registry readiness and model states.
        """
        manifests = self.list_manifests()
        model_states = []
        
        for name in manifests:
            try:
                manifest = self.load_manifest(name)
                status = self.verify_model(manifest)
                model_states.append({
                    "name": name,
                    "version": manifest.version,
                    "gguf_path": manifest.gguf_path,
                    "checksum_status": status.value,
                    "verified": status == ChecksumStatus.VERIFIED,
                })
            except Exception as e:
                model_states.append({
                    "name": name,
                    "version": None,
                    "gguf_path": None,
                    "checksum_status": "error",
                    "verified": False,
                    "error": str(e),
                })
        
        verified_count = sum(1 for m in model_states if m["verified"])
        
        return {
            "ready": verified_count > 0,
            "total_manifests": len(manifests),
            "verified_models": verified_count,
            "models": model_states,
        }
