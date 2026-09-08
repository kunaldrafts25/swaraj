"""Router module for SWARAJ v2.

Provides explainable, deterministic model routing based on:
- Task characteristics (embedding-based classification)
- Model capability vectors from real benchmarks
- Hardware tier constraints
- Latency budgets
"""

from swaraj.router.embed import TaskEmbedder, EmbeddingUnavailableError
from swaraj.router.classifier import TaskClassifier, TaskCharacteristics
from swaraj.router.decide import (
    RouterDecisionEngine,
    RoutingDecision,
    RouterUnavailableError,
    ModelNotBenchmarkedError,
    NoEligibleModelError,
)

__all__ = [
    "TaskEmbedder",
    "EmbeddingUnavailableError",
    "TaskClassifier",
    "TaskCharacteristics",
    "RouterDecisionEngine",
    "RoutingDecision",
    "RouterUnavailableError",
    "ModelNotBenchmarkedError",
    "NoEligibleModelError",
]
