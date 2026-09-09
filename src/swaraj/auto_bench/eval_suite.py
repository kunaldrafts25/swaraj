"""Deterministic evaluation suite for model capability benchmarking.

This module provides micro-tasks for evaluating model capabilities in:
- Code generation/correctness
- Summarization
- OCR-to-structured-field extraction

IMPORTANT: This module returns None scores until actual model evaluation is performed.
Never fake benchmark scores. The eval suite provides the task definitions and
scoring logic, but actual scores require running the model against these tasks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import hashlib


@dataclass(frozen=True)
class EvalTask(ABC):
    """Base class for deterministic evaluation tasks."""

    task_id: str
    description: str
    expected_output: str

    @abstractmethod
    def score(self, model_output: str) -> float:
        """Score model output against expected output. Returns 0.0-1.0."""
        pass


@dataclass(frozen=True)
class CodeTask(EvalTask):
    """Code generation/correctness evaluation task."""

    task_id: str = "code_001"
    description: str = "Generate a Python function to calculate factorial"
    expected_output: str = "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)"

    def score(self, model_output: str) -> float:
        """Score code correctness based on structural match and key patterns."""
        output_lower = model_output.lower().strip()
        expected_lower = self.expected_output.lower()

        # Check for required patterns (deterministic scoring)
        score = 0.0
        checks = [
            "def" in output_lower,
            "factorial" in output_lower,
            "return" in output_lower,
            "if" in output_lower or "else" in output_lower,
            "n" in output_lower,
        ]

        passed = sum(checks)
        score = passed / len(checks)

        # Bonus for exact match
        if expected_lower in output_lower or output_lower in expected_lower:
            score = max(score, 0.95)

        return round(score, 4)


@dataclass(frozen=True)
class SummaryTask(EvalTask):
    """Text summarization evaluation task."""

    task_id: str = "summary_001"
    description: str = "Summarize a refinery inspection report into key findings"
    expected_output: str = "Inspection found 3 critical issues: pipe corrosion, valve leak, pressure anomaly"

    def score(self, model_output: str) -> float:
        """Score summarization quality based on key concept coverage."""
        output_lower = model_output.lower()

        # Key concepts that should appear in a good summary
        key_concepts = [
            "inspection",
            "corrosion",
            "leak",
            "pressure",
            "issue" or "problem" or "finding",
        ]

        # Count how many key concepts are present
        matches = sum(1 for concept in key_concepts if concept in output_lower)
        score = matches / len(key_concepts)

        return round(score, 4)


@dataclass(frozen=True)
class OCRExtractTask(EvalTask):
    """OCR-to-structured-field extraction evaluation task."""

    task_id: str = "ocr_extract_001"
    description: str = "Extract pressure reading from scanned gauge image text"
    expected_output: str = '{"field": "pressure_reading", "value": "145.2", "unit": "psi"}'

    def score(self, model_output: str) -> float:
        """Score structured field extraction accuracy."""
        output_lower = model_output.lower()

        # Required elements for successful extraction
        checks = [
            "pressure" in output_lower,
            "145" in output_lower or "145.2" in output_lower,
            "psi" in output_lower,
            "{" in output_lower and "}" in output_lower,  # JSON-like structure
            "field" in output_lower or "value" in output_lower,
        ]

        passed = sum(checks)
        score = passed / len(checks)

        return round(score, 4)


class DeterministicEvalSuite:
    """Complete evaluation suite for model capability assessment.

    This suite runs all evaluation tasks and produces a capability vector.
    Scores are only valid after actual model execution against these tasks.
    """

    def __init__(self):
        self.tasks: tuple[EvalTask, ...] = (
            CodeTask(),
            SummaryTask(),
            OCRExtractTask(),
        )

    def get_task_by_type(self, task_type: str) -> Optional[EvalTask]:
        """Get a task by its type identifier."""
        type_map = {
            "code": self.tasks[0],
            "summary": self.tasks[1],
            "ocr_extract": self.tasks[2],
        }
        return type_map.get(task_type)

    def run_evaluation(self, model_runner, model_id: str) -> dict[str, Optional[float]]:
        """Run all evaluation tasks against a model.

        Args:
            model_runner: Callable that takes (prompt) and returns model output string
            model_id: Identifier for the model being evaluated

        Returns:
            Dictionary mapping capability names to scores (None if evaluation failed)

        IMPORTANT: If model_runner cannot execute (model not loaded, etc.),
        this method returns None scores rather than fabricating values.
        """
        scores: dict[str, Optional[float]] = {}

        for task in self.tasks:
            try:
                # Extract prompt from task description
                prompt = f"Task: {task.description}\n\nExpected format: {task.expected_output}"

                # Run model inference
                output = model_runner(prompt)

                if output is None:
                    scores[task.task_id.split("_")[0]] = None
                    continue

                # Score the output
                score = task.score(output)
                scores[task.task_id.split("_")[0]] = score

            except Exception:
                # Model execution failed - return None, don't fake scores
                scores[task.task_id.split("_")[0]] = None

        return scores

    def generate_benchmark_hash(self, scores: dict[str, Optional[float]]) -> str:
        """Generate a deterministic hash of benchmark results for integrity verification."""
        # Sort keys for determinism
        sorted_items = sorted(scores.items())
        # Convert to string representation
        score_str = ",".join(f"{k}={v}" for k, v in sorted_items)
        # Hash the representation
        return hashlib.sha256(score_str.encode()).hexdigest()[:16]
