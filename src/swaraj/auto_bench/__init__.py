"""Auto-benchmarking module for SWARAJ v2.

Provides deterministic micro-evaluation suites for model capability assessment.
"""

from swaraj.auto_bench.eval_suite import (
    CodeTask,
    SummaryTask,
    OCRExtractTask,
    DeterministicEvalSuite,
)
from swaraj.auto_bench.capability_vector import (
    CapabilityVector,
    CapabilityVectorCalculator,
    CapabilityVectorStorage,
)

__all__ = [
    "CodeTask",
    "SummaryTask",
    "OCRExtractTask",
    "DeterministicEvalSuite",
    "CapabilityVector",
    "CapabilityVectorCalculator",
    "CapabilityVectorStorage",
]
