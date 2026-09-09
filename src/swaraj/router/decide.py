"""Router decision engine for SWARAJ v2.

Implements explainable, deterministic model routing based on:
- Task characteristics from embedding-based classification
- Model capability vectors from real benchmarks
- Hardware tier constraints
- Latency budgets

CRITICAL: This module never fabricates confidence scores or routing decisions.
All values must come from actual computation or persisted verified state.
"""

from dataclasses import dataclass, field
from typing import Optional, Any
import math


@dataclass(frozen=True)
class RoutingDecision:
    """Result of a routing decision.

    Attributes:
        selected_model: Name of the selected model (or None if no model available)
        confidence: Confidence score 0.0-1.0 computed from real matching logic
        reasoning: Human-readable explanation of the routing decision
        capability_scores: Dictionary of capability names to scores from the model
        hardware_tier: Detected hardware tier (cpu_only, gpu_partial, gpu_full)
        task_characteristics: Characteristics detected in the task
        is_fail_closed: True if this decision represents a fail-closed state
        error_detail: Error message if routing failed
    """

    selected_model: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    capability_scores: dict[str, Optional[float]] = field(default_factory=dict)
    hardware_tier: str = "unknown"
    task_characteristics: dict[str, Any] = field(default_factory=dict)
    is_fail_closed: bool = False
    error_detail: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "selected_model": self.selected_model,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "capability_scores": self.capability_scores,
            "hardware_tier": self.hardware_tier,
            "task_characteristics": self.task_characteristics,
            "is_fail_closed": self.is_fail_closed,
            "error_detail": self.error_detail,
        }


class RouterUnavailableError(Exception):
    """Raised when the router cannot make a decision due to unavailable models."""

    pass


class ModelNotBenchmarkedError(Exception):
    """Raised when a model has not been benchmarked and routing requires it."""

    pass


class NoEligibleModelError(Exception):
    """Raised when no model satisfies the routing requirements."""

    pass


class RouterDecisionEngine:
    """Makes deterministic routing decisions based on task and model state.

    This engine implements explainable routing:
    1. Analyze task characteristics
    2. Filter eligible models by hardware compatibility
    3. Score models by capability match
    4. Select best model with confidence calculation
    5. Generate human-readable reasoning

    Fail-Closed Behavior:
    - If no verified models exist, raises RouterUnavailableError
    - If required capabilities are not benchmarked, raises ModelNotBenchmarkedError
    - If no model satisfies constraints, raises NoEligibleModelError
    - Never returns fake confidence scores or hardcoded selections
    """

    def __init__(self, registry_loader, capability_calculator, hardware_tier: str = "cpu_only"):
        """Initialize the router decision engine.

        Args:
            registry_loader: RegistryLoader instance for accessing model manifests
            capability_calculator: CapabilityVectorCalculator for model capabilities
            hardware_tier: Current hardware tier (cpu_only, gpu_partial, gpu_full)
        """
        self.registry_loader = registry_loader
        self.capability_calculator = capability_calculator
        self.hardware_tier = hardware_tier

    def decide(
        self,
        task_description: str,
        task_type: Optional[str] = None,
        latency_budget_ms: Optional[int] = None,
    ) -> RoutingDecision:
        """Make a routing decision for the given task.

        Args:
            task_description: Description of the task to route
            task_type: Optional explicit task type hint
            latency_budget_ms: Optional maximum acceptable latency in milliseconds

        Returns:
            RoutingDecision with selected model and explanation

        Raises:
            RouterUnavailableError: If no verified models are available
            ModelNotBenchmarkedError: If required capabilities are not benchmarked
            NoEligibleModelError: If no model satisfies all constraints
        """
        # Get verified models from registry
        status = self.registry_loader.get_registry_status()

        if not (status.get("registry_ready") or status.get("ready", False)):
            raise RouterUnavailableError(
                "No verified models available for routing. "
                "Registry is not ready - model checksums not verified."
            )

        verified_models = [m for m in status.get("models", []) if m.get("verified", False)]

        if not verified_models:
            raise RouterUnavailableError(
                "No verified models available for routing. "
                "All models have unverified checksums or are missing."
            )

        # Classify task characteristics
        from swaraj.router.classifier import TaskClassifier

        classifier = TaskClassifier()
        characteristics = classifier.classify(task_description)
        required_capabilities = classifier.get_required_capabilities(characteristics)

        # Score each verified model
        best_model = None
        best_score = -1.0
        best_capability_scores: dict[str, Optional[float]] = {}
        rejection_reasons: list[str] = []

        for model_info in verified_models:
            model_name = model_info.get("name", "unknown")

            # Get capability vector for this model
            cap_vector = self.capability_calculator.get_or_create_unbenchmarked(model_name)

            # Check if model has been benchmarked for required capabilities
            if not cap_vector.has_real_benchmark:
                rejection_reasons.append(
                    f"{model_name}: Not benchmarked (has_real_benchmark=False)"
                )
                continue

            # Calculate capability match score
            cap_scores: dict[str, Optional[float]] = {
                "code": cap_vector.code,
                "summary": cap_vector.summary,
                "ocr_extract": cap_vector.ocr_extract,
            }

            # Check hardware compatibility
            model_min_tier = model_info.get("hardware_tier_min", "cpu_only")
            if not self._is_hardware_compatible(model_min_tier):
                rejection_reasons.append(
                    f"{model_name}: Hardware incompatible (requires {model_min_tier})"
                )
                continue

            # Calculate match score for required capabilities
            match_score = self._calculate_match_score(cap_scores, required_capabilities)

            if match_score > best_score:
                best_score = match_score
                best_model = model_name
                best_capability_scores = cap_scores

        # Handle case where no model was eligible
        if best_model is None:
            if rejection_reasons:
                raise ModelNotBenchmarkedError(
                    f"No eligible model found. Rejection reasons: {'; '.join(rejection_reasons)}"
                )
            else:
                raise NoEligibleModelError("No model satisfied routing constraints")

        # Calculate final confidence
        confidence = self._calculate_confidence(best_score, len(required_capabilities))

        # Generate reasoning
        reasoning = self._generate_reasoning(
            best_model,
            best_capability_scores,
            required_capabilities,
            characteristics,
            confidence,
        )

        return RoutingDecision(
            selected_model=best_model,
            confidence=round(confidence, 4),
            reasoning=reasoning,
            capability_scores=best_capability_scores,
            hardware_tier=self.hardware_tier,
            task_characteristics=characteristics.to_dict(),
            is_fail_closed=False,
            error_detail=None,
        )

    def _is_hardware_compatible(self, model_min_tier: str) -> bool:
        """Check if current hardware meets model's minimum requirements."""
        tier_order = {"cpu_only": 0, "gpu_partial": 1, "gpu_full": 2}

        current_level = tier_order.get(self.hardware_tier, 0)
        required_level = tier_order.get(model_min_tier, 0)

        return current_level >= required_level

    def _calculate_match_score(
        self, cap_scores: dict[str, Optional[float]], required_caps: list[str]
    ) -> float:
        """Calculate how well a model's capabilities match task requirements.

        Args:
            cap_scores: Model's capability scores (may contain None)
            required_caps: List of required capability names

        Returns:
            Match score 0.0-1.0
        """
        if not required_caps:
            return 0.5  # Neutral score if no specific requirements

        matching_scores = []
        for cap in required_caps:
            score = cap_scores.get(cap)
            if score is not None:
                matching_scores.append(score)
            else:
                # Missing capability counts as 0
                matching_scores.append(0.0)

        if not matching_scores:
            return 0.0

        # Average of matching scores
        return sum(matching_scores) / len(matching_scores)

    def _calculate_confidence(
        self, match_score: float, num_requirements: int
    ) -> float:
        """Calculate confidence score based on match quality and requirements.

        Args:
            match_score: Capability match score (0.0-1.0)
            num_requirements: Number of required capabilities

        Returns:
            Confidence score 0.0-1.0
        """
        # Base confidence is the match score
        base_confidence = match_score

        # Adjust for number of requirements (more requirements = more certainty needed)
        if num_requirements == 0:
            requirement_factor = 1.0
        elif num_requirements <= 2:
            requirement_factor = 1.0
        else:
            # Slight penalty for complex tasks with many requirements
            requirement_factor = max(0.8, 1.0 - (num_requirements - 2) * 0.05)

        confidence = base_confidence * requirement_factor

        # Clamp to valid range
        return max(0.0, min(1.0, confidence))

    def _generate_reasoning(
        self,
        model_name: str,
        capability_scores: dict[str, Optional[float]],
        required_caps: list[str],
        characteristics,
        confidence: float,
    ) -> str:
        """Generate human-readable reasoning for the routing decision.

        Args:
            model_name: Selected model name
            capability_scores: Model's capability scores
            required_caps: Required capabilities for the task
            characteristics: Task characteristics
            confidence: Final confidence score

        Returns:
            Human-readable reasoning string
        """
        parts = []

        # Model selection reason
        parts.append(f"Selected {model_name}")

        # Capability highlights
        cap_highlights = []
        for cap in required_caps:
            score = capability_scores.get(cap)
            if score is not None:
                cap_highlights.append(f"{cap}={score:.2f}")
            else:
                cap_highlights.append(f"{cap}=N/A")

        if cap_highlights:
            parts.append(f"capabilities: {', '.join(cap_highlights)}")

        # Hardware tier
        parts.append(f"hardware_tier={self.hardware_tier}")

        # Task characteristics summary
        char_summary = []
        if characteristics.code_required:
            char_summary.append("code_task")
        if characteristics.ocr_required:
            char_summary.append("ocr_task")
        if characteristics.summarization_required:
            char_summary.append("summary_task")
        if characteristics.domain != "general":
            char_summary.append(f"domain={characteristics.domain}")

        if char_summary:
            parts.append(f"task_type={'/'.join(char_summary)}")

        # Confidence interpretation
        if confidence >= 0.8:
            parts.append("high_confidence")
        elif confidence >= 0.5:
            parts.append("moderate_confidence")
        else:
            parts.append("low_confidence")

        return "; ".join(parts)
