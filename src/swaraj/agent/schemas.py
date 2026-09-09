"""SWARAJ Agent Schemas - Pydantic models for agent workflow."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Supported task types for routing and execution."""

    OCR_EXTRACTION = "ocr_extraction"
    SUMMARIZATION = "summarization"
    CODE_GENERATION = "code_generation"
    DOCUMENT_GENERATION = "document_generation"
    DATA_ANALYSIS = "data_analysis"
    APPROVAL_REQUEST = "approval_request"


class RunState(str, Enum):
    """Agent run state machine states."""

    PENDING = "pending"
    PLANNING = "planning"
    PRUNING = "pruning"
    ACTING = "acting"
    OBSERVING = "observing"
    SELF_CHECK = "self_check"
    REGENERATING = "regenerating"
    CERTIFYING = "certifying"
    COMPLETED = "completed"
    FAILED = "failed"
    SECURITY_FAILED = "security_failed"


class TaskInput(BaseModel):
    """Input task specification."""

    task_description: str = Field(..., description="Natural language task description")
    task_type: Optional[TaskType] = Field(None, description="Explicit task type if known")
    user_id: str = Field(..., description="User identifier")
    role: str = Field(..., description="User role for RBAC")
    source_documents: List[str] = Field(
        default_factory=list, description="List of source document filenames"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None, description="Expected output schema for validation"
    )
    run_id: Optional[str] = Field(None, description="Optional pre-assigned run ID")


class PlannedStep(BaseModel):
    """A single step in the agent plan."""

    step_id: str = Field(..., description="Unique step identifier")
    action: str = Field(..., description="Action to perform (e.g., read_file, write_docx)")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Action parameters"
    )
    description: str = Field(..., description="Human-readable step description")
    requires_approval: bool = Field(
        False, description="Whether this step requires human approval"
    )


class AgentPlan(BaseModel):
    """Complete agent execution plan."""

    run_id: str = Field(..., description="Associated run ID")
    steps: List[PlannedStep] = Field(..., description="Ordered list of planned steps")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    total_steps: int = Field(..., description="Total number of steps")


class RBACDecision(str, Enum):
    """RBAC evaluation result."""

    ALLOWED = "allowed"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"


class RBACResult(BaseModel):
    """Result of RBAC evaluation for a step."""

    step_id: str = Field(..., description="Step being evaluated")
    decision: RBACDecision = Field(..., description="RBAC decision")
    reason: Optional[str] = Field(None, description="Reason for denial or approval requirement")
    approval_id: Optional[str] = Field(
        None, description="Approval request ID if approval required"
    )
    user_id: str = Field(..., description="User requesting action")
    role: str = Field(..., description="User role")


class ToolInvocation(BaseModel):
    """Record of a tool invocation."""

    step_id: str = Field(..., description="Associated step ID")
    tool_name: str = Field(..., description="Name of tool invoked")
    arguments: Dict[str, Any] = Field(..., description="Tool arguments")
    invoked_at: datetime = Field(default_factory=datetime.utcnow)
    invoked_by: str = Field(..., description="User who invoked the tool")


class Observation(BaseModel):
    """Result observed from tool execution."""

    step_id: str = Field(..., description="Associated step ID")
    tool_name: str = Field(..., description="Tool that produced observation")
    success: bool = Field(..., description="Whether tool execution succeeded")
    result: Optional[Any] = Field(None, description="Tool result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    observed_at: datetime = Field(default_factory=datetime.utcnow)
    source_references: List[str] = Field(
        default_factory=list, description="Source document references"
    )


class ValidationSeverity(str, Enum):
    """Severity level of validation error."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ValidationError(BaseModel):
    """Single validation error from self-check."""

    field: str = Field(..., description="Field or section with issue")
    issue: str = Field(..., description="Description of the issue")
    severity: ValidationSeverity = Field(
        ValidationSeverity.CRITICAL, description="Error severity"
    )
    suggested_fix: Optional[str] = Field(None, description="Suggested remediation")


class SelfCheckResult(BaseModel):
    """Result of reflexive self-check validation."""

    valid: bool = Field(..., description="Whether document passed validation")
    errors: List[ValidationError] = Field(
        default_factory=list, description="List of validation errors"
    )
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    iteration: int = Field(..., description="Self-check iteration number")
    document_path: Optional[str] = Field(None, description="Path to checked document")
    document_type: Optional[str] = Field(None, description="Type of document (docx/xlsx)")


class CertificateRequest(BaseModel):
    """Request to generate certificate for a run."""

    run_id: str = Field(..., description="Run to certify")
    user_id: str = Field(..., description="Requesting user")
    force: bool = Field(False, description="Force certification even with warnings")


class RunStatus(BaseModel):
    """Current status of an agent run."""

    run_id: str = Field(..., description="Run identifier")
    state: RunState = Field(..., description="Current state")
    user_id: str = Field(..., description="Owning user")
    role: str = Field(..., description="User role")
    started_at: Optional[datetime] = Field(None, description="Run start time")
    completed_at: Optional[datetime] = Field(None, description="Run completion time")
    current_step: Optional[int] = Field(None, description="Current step index")
    total_steps: Optional[int] = Field(None, description="Total planned steps")
    self_check_iterations: int = Field(0, description="Number of self-check iterations")
    security_status: str = Field("ok", description="Security monitoring status")
    certificate_eligible: bool = Field(False, description="Whether run can be certified")
    failure_reason: Optional[str] = Field(None, description="Reason for failure if failed")


class AgentState(BaseModel):
    """Complete agent state for LangGraph workflow."""

    run_id: str = Field(..., description="Unique run identifier")
    task_input: TaskInput = Field(..., description="Original task input")
    plan: Optional[AgentPlan] = Field(None, description="Generated execution plan")
    rbac_results: List[RBACResult] = Field(
        default_factory=list, description="RBAC evaluation results"
    )
    invocations: List[ToolInvocation] = Field(
        default_factory=list, description="Tool invocations"
    )
    observations: List[Observation] = Field(
        default_factory=list, description="Tool execution results"
    )
    self_check_results: List[SelfCheckResult] = Field(
        default_factory=list, description="Self-check history"
    )
    current_state: RunState = Field(RunState.PENDING, description="Current workflow state")
    iteration_count: int = Field(0, description="Act/self-check iteration counter")
    max_iterations: int = Field(4, description="Maximum allowed iterations")
    security_failed: bool = Field(False, description="Whether security failure occurred")
    egress_violations: List[Dict[str, Any]] = Field(
        default_factory=list, description="Recorded egress violations"
    )
    generated_artifacts: List[str] = Field(
        default_factory=list, description="Paths to generated documents"
    )
    approval_queue: List[str] = Field(
        default_factory=list, description="Pending approval request IDs"
    )
    trace: List[Dict[str, Any]] = Field(
        default_factory=list, description="Complete execution trace"
    )
    failure_reason: Optional[str] = Field(None, description="Reason for failure if failed")
    certificate_eligible: bool = Field(False, description="Whether run can be certified")

    def add_trace_entry(self, event: str, details: Dict[str, Any]) -> None:
        """Add an entry to the execution trace."""
        from datetime import datetime

        self.trace.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "event": event,
                "state": self.current_state.value,
                "iteration": self.iteration_count,
                "details": details,
            }
        )
