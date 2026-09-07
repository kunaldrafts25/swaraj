"""Manifest schema definitions for SWARAJ v2 model registry.

All manifests must validate against these schemas using Pydantic.
Security-critical fields (sha256, signature) are strictly validated.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, field_validator, ConfigDict


class HardwareTier(str, Enum):
    """Hardware tier classifications for model requirements.
    
    REQ-006: Hardware Tier Requirements
    """
    CPU_ONLY = "cpu_only"
    GPU_4GB = "gpu_4gb"
    GPU_6GB_PLUS = "gpu_6gb_plus"


class ChecksumStatus(str, Enum):
    """Status of checksum verification.
    
    REQ-173: Model SHA256 Verification
    REQ-174: Fail-Closed on Mismatch
    """
    VERIFIED = "verified"
    PENDING = "pending"
    MISMATCH = "mismatch"
    MISSING = "missing"
    PLACEHOLDER = "placeholder"


class CapabilityVector(BaseModel):
    """Capability scores from auto-benchmarking.
    
    REQ-007: Capability-vector auto-benchmarking
    REQ-178: No Fake Benchmark Scores
    
    Scores must be in range [0.0, 1.0] and represent actual measured performance.
    Before real benchmarking, this may be absent or marked as pending.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    code: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Code generation/correctness score",
    )
    summary: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Summarization score",
    )
    ocr_extract: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="OCR-to-structured-field extraction score",
    )
    
    @field_validator("code", "summary", "ocr_extract")
    @classmethod
    def validate_score_range(cls, v: Optional[float]) -> Optional[float]:
        """Validate that scores are in valid range if present."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError(f"Score must be between 0.0 and 1.0, got {v}")
        return v
    
    def is_pending(self) -> bool:
        """Return True if no real benchmark scores are present."""
        return all(score is None for score in [self.code, self.summary, self.ocr_extract])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class ModelManifest(BaseModel):
    """Schema for model registry manifests.
    
    REQ-013: Registry Contract
    REQ-173: Model SHA256 Verification
    REQ-174: Fail-Closed on Mismatch
    
    All fields are required. The manifest must be signed and include
    a verified SHA256 checksum of the GGUF artifact.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="Model identifier (e.g., qwen3-4b-instruct)",
    )
    version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        pattern=r"^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9]+)?$",
        description="Semantic version (e.g., 1.0.0)",
    )
    gguf_path: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Relative path to GGUF artifact from models directory",
    )
    sha256: str = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
        description="SHA256 checksum of GGUF artifact (lowercase hex, 64 chars)",
    )
    quant: str = Field(
        ...,
        min_length=1,
        max_length=32,
        pattern=r"^[A-Z0-9_]+$",
        description="Quantization type (e.g., Q4_K_M)",
    )
    context_length: int = Field(
        ...,
        gt=0,
        le=131072,
        description="Maximum context length in tokens",
    )
    hardware_tier_min: HardwareTier = Field(
        ...,
        description="Minimum hardware tier required",
    )
    capability_vector: Optional[CapabilityVector] = Field(
        default=None,
        description="Auto-benchmarked capability scores (may be pending)",
    )
    signed_at: datetime = Field(
        ...,
        description="ISO 8601 timestamp of manifest signing (UTC)",
    )
    signature: str = Field(
        ...,
        min_length=1,
        description="Cryptographic signature of manifest content",
    )
    
    @field_validator("signed_at")
    @classmethod
    def validate_signed_at_utc(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
    
    @field_validator("sha256")
    @classmethod
    def validate_sha256_format(cls, v: str) -> str:
        """Validate SHA256 is proper hex format."""
        try:
            bytes.fromhex(v)
        except ValueError:
            raise ValueError("SHA256 must be valid hexadecimal string")
        return v.lower()
    
    def is_checksum_placeholder(self) -> bool:
        """Check if SHA256 is a placeholder value.
        
        REQ-175: Reject Placeholder/fabricated checksums
        """
        placeholder_patterns = [
            "0" * 64,
            "f" * 64,
            "deadbeef" * 8,
            "cafe" * 16,
            "todo",
            "pending",
            "placeholder",
            "changeme",
            "replace_me",
        ]
        sha_lower = self.sha256.lower()
        return any(
            sha_lower == p or sha_lower == p.upper()
            for p in placeholder_patterns
            if len(p) == 64 or p in ["todo", "pending", "placeholder", "changeme", "replace_me"]
        ) or (
            len(self.sha256) == 64 and
            self.sha256.lower() in ["0" * 64, "f" * 64, "deadbeef" * 8]
        )
    
    def get_checksum_status(self, actual_sha256: Optional[str]) -> ChecksumStatus:
        """Determine checksum verification status.
        
        Args:
            actual_sha256: The calculated SHA256 of the artifact, or None if missing.
        
        Returns:
            ChecksumStatus indicating verification result.
        """
        if actual_sha256 is None:
            return ChecksumStatus.MISSING
        
        if self.is_checksum_placeholder():
            return ChecksumStatus.PLACEHOLDER
        
        if actual_sha256.lower() == self.sha256.lower():
            return ChecksumStatus.VERIFIED
        
        return ChecksumStatus.MISMATCH
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = self.model_dump(mode="json")
        if self.capability_vector:
            result["capability_vector"] = self.capability_vector.to_dict()
        return result
