"""Model registry for SWARAJ v2.

Provides schema validation, checksum verification, and fail-closed model loading.
"""

from swaraj.registry.manifest_schema import (
    ModelManifest,
    CapabilityVector,
    HardwareTier,
    ChecksumStatus,
)
from swaraj.registry.loader import (
    RegistryLoader,
    RegistryError,
    ChecksumMismatchError,
    ModelNotFoundError,
    ManifestValidationError,
    PathTraversalError,
)

__all__ = [
    "ModelManifest",
    "CapabilityVector",
    "HardwareTier",
    "ChecksumStatus",
    "RegistryLoader",
    "RegistryError",
    "ChecksumMismatchError",
    "ModelNotFoundError",
    "ManifestValidationError",
    "PathTraversalError",
]
