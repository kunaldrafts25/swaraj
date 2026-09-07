"""Capability vector calculation and persistence for model benchmarking.

This module handles:
- Capability vector data structure
- Calculation of capability scores from benchmark results
- Persistence of verified capability vectors to disk
- Detection of unbenchmarked or placeholder capability data

CRITICAL: Never fabricate capability scores. If a model has not been benchmarked,
the capability vector must indicate this explicitly rather than providing fake values.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone


@dataclass(frozen=True)
class CapabilityVector:
    """Represents a model's capability scores across different task types.

    Attributes:
        code: Code generation/correctness score (0.0-1.0) or None if not benchmarked
        summary: Text summarization score (0.0-1.0) or None if not benchmarked
        ocr_extract: OCR field extraction score (0.0-1.0) or None if not benchmarked
        has_real_benchmark: True only if scores come from actual benchmark execution
        benchmark_hash: Hash of benchmark results for integrity verification
        benchmarked_at: ISO timestamp of when benchmarking was performed
    """

    code: Optional[float] = None
    summary: Optional[float] = None
    ocr_extract: Optional[float] = None
    has_real_benchmark: bool = False
    benchmark_hash: Optional[str] = None
    benchmarked_at: Optional[str] = None

    def is_complete(self) -> bool:
        """Check if all capability scores are present and from real benchmarks."""
        return (
            self.has_real_benchmark
            and self.code is not None
            and self.summary is not None
            and self.ocr_extract is not None
        )

    def get_score(self, capability: str) -> Optional[float]:
        """Get a specific capability score by name."""
        return getattr(self, capability, None)

    def average_score(self) -> Optional[float]:
        """Calculate average of available scores. Returns None if no scores exist."""
        scores = [s for s in [self.code, self.summary, self.ocr_extract] if s is not None]
        if not scores:
            return None
        return round(sum(scores) / len(scores), 4)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CapabilityVector":
        """Create from dictionary."""
        return cls(
            code=data.get("code"),
            summary=data.get("summary"),
            ocr_extract=data.get("ocr_extract"),
            has_real_benchmark=data.get("has_real_benchmark", False),
            benchmark_hash=data.get("benchmark_hash"),
            benchmarked_at=data.get("benchmarked_at"),
        )


class CapabilityVectorStorage:
    """Persistent storage for capability vectors.

    Stores capability vectors in a JSON file for later retrieval.
    Only stores vectors that have been verified through actual benchmarking.
    """

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self._ensure_directory()

    def _ensure_directory(self):
        """Ensure the storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, model_id: str, vector: CapabilityVector) -> None:
        """Save a capability vector for a model.

        Only saves if the vector has real benchmark data.
        """
        if not vector.has_real_benchmark:
            raise ValueError(
                f"Cannot save capability vector for {model_id}: "
                "no real benchmark data. Refusing to persist unverified scores."
            )

        data = self._load_all()
        data[model_id] = vector.to_dict()
        self._save_all(data)

    def load(self, model_id: str) -> Optional[CapabilityVector]:
        """Load a capability vector for a model.

        Returns None if no verified vector exists for the model.
        """
        data = self._load_all()
        if model_id not in data:
            return None

        vector = CapabilityVector.from_dict(data[model_id])

        # Verify the vector has real benchmark data
        if not vector.has_real_benchmark:
            return None

        return vector

    def list_models(self) -> list[str]:
        """List all models with verified capability vectors."""
        data = self._load_all()
        return list(data.keys())

    def _load_all(self) -> dict:
        """Load all capability vectors from storage."""
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_all(self, data: dict) -> None:
        """Save all capability vectors to storage."""
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)


class CapabilityVectorCalculator:
    """Calculates capability vectors from benchmark results.

    This class takes raw benchmark scores and produces validated capability vectors.
    It ensures that only genuine benchmark results are used - never fabricated scores.
    """

    def __init__(self, storage: CapabilityVectorStorage):
        self.storage = storage

    def calculate_from_scores(
        self,
        model_id: str,
        scores: dict[str, Optional[float]],
        benchmark_hash: Optional[str] = None,
    ) -> CapabilityVector:
        """Calculate a capability vector from benchmark scores.

        Args:
            model_id: Identifier for the model
            scores: Dictionary mapping capability names to scores
                    (may contain None for failed evaluations)
            benchmark_hash: Optional hash of benchmark results for integrity

        Returns:
            CapabilityVector with has_real_benchmark=True if any valid scores exist,
            otherwise has_real_benchmark=False

        IMPORTANT: If all scores are None, returns a vector with has_real_benchmark=False.
        This signals that the model has not been successfully benchmarked.
        """
        # Check if we have any valid scores
        valid_scores = {k: v for k, v in scores.items() if v is not None}

        if not valid_scores:
            # No valid scores - return unbenchmarked vector
            return CapabilityVector(
                code=None,
                summary=None,
                ocr_extract=None,
                has_real_benchmark=False,
                benchmark_hash=None,
                benchmarked_at=None,
            )

        # Map scores to capability vector fields
        code_score = valid_scores.get("code")
        summary_score = valid_scores.get("summary")
        ocr_score = valid_scores.get("ocr_extract")

        vector = CapabilityVector(
            code=code_score,
            summary=summary_score,
            ocr_extract=ocr_score,
            has_real_benchmark=True,
            benchmark_hash=benchmark_hash,
            benchmarked_at=datetime.now(timezone.utc).isoformat(),
        )

        # Persist the verified vector
        self.storage.save(model_id, vector)

        return vector

    def get_or_create_unbenchmarked(self, model_id: str) -> CapabilityVector:
        """Get existing capability vector or create an unbenchmarked one.

        This method is used when routing decisions need capability information
        but the model may not have been benchmarked yet.

        Returns:
            Existing verified vector if available, otherwise an unbenchmarked vector
            with has_real_benchmark=False
        """
        existing = self.storage.load(model_id)
        if existing is not None:
            return existing

        # Return unbenchmarked vector - DO NOT FABRICATE SCORES
        return CapabilityVector(
            code=None,
            summary=None,
            ocr_extract=None,
            has_real_benchmark=False,
            benchmark_hash=None,
            benchmarked_at=None,
        )

    def is_benchmarked(self, model_id: str) -> bool:
        """Check if a model has been successfully benchmarked."""
        vector = self.storage.load(model_id)
        return vector is not None and vector.is_complete()
