"""SWARAJ Agent Graph - LangGraph workflow implementation."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import uuid

from swaraj.agent.schemas import (
    AgentState,
    RunState,
    TaskInput,
    AgentPlan,
    PlannedStep,
    RBACResult,
    RBACDecision,
    ToolInvocation,
    Observation,
    SelfCheckResult,
    ValidationError,
    ValidationSeverity,
)
from swaraj.governance.rbac import RBACManager
from swaraj.tools.docx_writer import DocXWriter
from swaraj.tools.xlsx_writer import XLSXWriter
from swaraj.tools.fs_jail import FilesystemJail


class AgentGraph:
    """LangGraph-based agent workflow orchestrator.
    
    Workflow: plan → prune → act → observe → self_check
                                         ├─ fail → act (max 4 iterations)
                                         └─ pass → cert (if no security failure)
    """

    def __init__(
        self,
        rbac_manager: RBACManager,
        filesystem_jail: FilesystemJail,
        workspace_root: str,
    ):
        self.rbac_manager = rbac_manager
        self.filesystem_jail = filesystem_jail
        self.workspace_root = workspace_root

    def create_run(self, task_input: TaskInput) -> AgentState:
        """Initialize a new agent run."""
        run_id = task_input.run_id or str(uuid.uuid4())
        state = AgentState(
            run_id=run_id,
            task_input=task_input,
            current_state=RunState.PENDING,
        )
        state.add_trace_entry("run_created", {"task_type": task_input.task_type})
        return state

    def plan(self, state: AgentState) -> AgentState:
        """Generate execution plan from task input."""
        state.current_state = RunState.PLANNING
        state.add_trace_entry("planning_started", {})

        steps = self._generate_plan(state.task_input)
        
        state.plan = AgentPlan(
            run_id=state.run_id,
            steps=steps,
            total_steps=len(steps),
        )
        
        state.add_trace_entry("plan_generated", {"step_count": len(steps)})
        return state

    def prune(self, state: AgentState) -> AgentState:
        """Apply RBAC pruning to the plan."""
        state.current_state = RunState.PRUNING
        state.add_trace_entry("rbac_pruning_started", {})

        if not state.plan:
            raise ValueError("Cannot prune: no plan exists")

        pruned_steps = []
        for step in state.plan.steps:
            result = self._evaluate_step_rbac(step, state.task_input.user_id, state.task_input.role)
            state.rbac_results.append(result)
            
            if result.decision == RBACDecision.ALLOWED:
                pruned_steps.append(step)
                state.add_trace_entry("step_allowed", {"step_id": step.step_id})
            elif result.decision == RBACDecision.APPROVAL_REQUIRED:
                state.approval_queue.append(result.approval_id or f"APR-{uuid.uuid4().hex[:8]}")
                state.add_trace_entry("step_requires_approval", {
                    "step_id": step.step_id,
                    "approval_id": result.approval_id,
                })
            else:
                state.add_trace_entry("step_denied", {
                    "step_id": step.step_id,
                    "reason": result.reason,
                })

        state.plan.steps = pruned_steps
        state.add_trace_entry("pruning_complete", {
            "original_count": len(state.plan.steps) + len([r for r in state.rbac_results if r.decision != RBACDecision.ALLOWED]),
            "pruned_count": len(pruned_steps),
        })
        return state

    def act(self, state: AgentState, step_index: int) -> AgentState:
        """Execute a single authorized step."""
        state.current_state = RunState.ACTING
        
        if not state.plan or step_index >= len(state.plan.steps):
            state.add_trace_entry("act_complete", {"reason": "no_more_steps"})
            return state

        step = state.plan.steps[step_index]
        state.add_trace_entry("executing_step", {"step_id": step.step_id, "action": step.action})

        invocation = ToolInvocation(
            step_id=step.step_id,
            tool_name=step.action,
            arguments=step.parameters,
            invoked_by=state.task_input.user_id,
        )
        state.invocations.append(invocation)

        observation = self._execute_tool(step, state)
        state.observations.append(observation)
        state.add_trace_entry("tool_executed", {
            "step_id": step.step_id,
            "success": observation.success,
        })

        return state

    def observe(self, state: AgentState) -> AgentState:
        """Process observations and update state."""
        state.current_state = RunState.OBSERVING
        state.add_trace_entry("observing", {"observation_count": len(state.observations)})
        return state

    def self_check(self, state: AgentState, document_path: Optional[str] = None, document_type: Optional[str] = None) -> AgentState:
        """Perform reflexive self-check on generated artifacts."""
        state.current_state = RunState.SELF_CHECK
        state.iteration_count += 1
        
        if state.iteration_count > state.max_iterations:
            state.current_state = RunState.FAILED
            state.failure_reason = f"Maximum self-check iterations ({state.max_iterations}) exceeded"
            state.add_trace_entry("max_iterations_exceeded", {"iteration": state.iteration_count})
            return state

        state.add_trace_entry("self_check_started", {"iteration": state.iteration_count})

        if not document_path:
            if state.generated_artifacts:
                document_path = state.generated_artifacts[-1]
            else:
                state.add_trace_entry("self_check_skipped", {"reason": "no_artifacts"})
                return state

        check_result = self._validate_document(document_path, document_type, state.iteration_count)
        state.self_check_results.append(check_result)

        if check_result.valid:
            state.add_trace_entry("self_check_passed", {"iteration": state.iteration_count})
        else:
            state.add_trace_entry("self_check_failed", {
                "iteration": state.iteration_count,
                "error_count": len(check_result.errors),
            })

        return state

    def should_regenerate(self, state: AgentState) -> bool:
        """Determine if regeneration is needed."""
        if not state.self_check_results:
            return False
        
        latest_check = state.self_check_results[-1]
        return (
            not latest_check.valid 
            and state.iteration_count < state.max_iterations
            and not state.security_failed
        )

    def can_certify(self, state: AgentState) -> Tuple[bool, Optional[str]]:
        """Determine if run can be certified."""
        if state.security_failed:
            return False, "Security failure detected during execution"
        
        if not state.self_check_results:
            return False, "No self-check performed"
        
        latest_check = state.self_check_results[-1]
        if not latest_check.valid:
            return False, f"Self-check validation failed: {[e.issue for e in latest_check.errors]}"
        
        if state.approval_queue:
            return False, "Pending approvals in queue"
        
        return True, None

    def _generate_plan(self, task_input: TaskInput) -> List[PlannedStep]:
        """Generate execution plan based on task type."""
        steps = []
        step_counter = 0

        # Always start with reading source documents
        for doc in task_input.source_documents:
            steps.append(PlannedStep(
                step_id=f"step-{step_counter}",
                action="read_document",
                parameters={"filename": doc},
                description=f"Read source document: {doc}",
                requires_approval=False,
            ))
            step_counter += 1

        # Add task-specific steps
        if task_input.task_type:
            if task_input.task_type.value == "document_generation":
                steps.append(PlannedStep(
                    step_id=f"step-{step_counter}",
                    action="write_docx",
                    parameters={"schema": task_input.output_schema},
                    description="Generate Word document",
                    requires_approval=True,
                ))
                step_counter += 1
            elif task_input.task_type.value == "data_analysis":
                steps.append(PlannedStep(
                    step_id=f"step-{step_counter}",
                    action="write_xlsx",
                    parameters={},
                    description="Generate Excel spreadsheet",
                    requires_approval=True,
                ))
                step_counter += 1

        return steps

    def _evaluate_step_rbac(self, step: PlannedStep, user_id: str, role: str) -> RBACResult:
        """Evaluate a single step against RBAC policy."""
        action_permitted = self.rbac_manager.check_permission(role, step.action)
        
        if action_permitted:
            return RBACResult(
                step_id=step.step_id,
                decision=RBACDecision.ALLOWED,
                user_id=user_id,
                role=role,
            )
        elif step.requires_approval:
            approval_id = self.rbac_manager.request_approval(
                user_id=user_id,
                role=role,
                action=step.action,
                parameters=step.parameters,
                reason=f"Step '{step.action}' requires approval for role '{role}'",
            )
            return RBACResult(
                step_id=step.step_id,
                decision=RBACDecision.APPROVAL_REQUIRED,
                reason=f"Action '{step.action}' requires approval",
                approval_id=approval_id,
                user_id=user_id,
                role=role,
            )
        else:
            return RBACResult(
                step_id=step.step_id,
                decision=RBACDecision.DENIED,
                reason=f"Action '{step.action}' not permitted for role '{role}'",
                user_id=user_id,
                role=role,
            )

    def _execute_tool(self, step: PlannedStep, state: AgentState) -> Observation:
        """Execute a tool based on step action."""
        try:
            if step.action == "read_document":
                filename = step.parameters.get("filename", "")
                safe_path = self.filesystem_jail.resolve_safe_path(filename)
                if safe_path.exists():
                    content = safe_path.read_text()
                    return Observation(
                        step_id=step.step_id,
                        tool_name=step.action,
                        success=True,
                        result={"content_preview": content[:500], "path": str(safe_path)},
                        source_references=[filename],
                    )
                else:
                    return Observation(
                        step_id=step.step_id,
                        tool_name=step.action,
                        success=False,
                        error=f"Document not found: {filename}",
                    )
            
            elif step.action == "write_docx":
                filename = f"output_{state.run_id[:8]}.docx"
                safe_path = self.filesystem_jail.resolve_safe_path(f"output/{filename}")
                safe_path.parent.mkdir(parents=True, exist_ok=True)
                
                writer = DocXWriter(str(self.filesystem_jail.workspace_root))
                title = state.task_input.task_description[:50]
                writer.write(safe_path.name, title=title)
                
                state.generated_artifacts.append(str(safe_path))
                return Observation(
                    step_id=step.step_id,
                    tool_name=step.action,
                    success=True,
                    result={"path": str(safe_path)},
                )
            
            elif step.action == "write_xlsx":
                filename = f"output_{state.run_id[:8]}.xlsx"
                safe_path = self.filesystem_jail.resolve_safe_path(f"output/{filename}")
                safe_path.parent.mkdir(parents=True, exist_ok=True)
                
                writer = XLSXWriter(str(self.filesystem_jail.workspace_root))
                writer.write(safe_path.name, sheet_name="Data")
                
                state.generated_artifacts.append(str(safe_path))
                return Observation(
                    step_id=step.step_id,
                    tool_name=step.action,
                    success=True,
                    result={"path": str(safe_path)},
                )
            
            else:
                return Observation(
                    step_id=step.step_id,
                    tool_name=step.action,
                    success=False,
                    error=f"Unknown action: {step.action}",
                )
        
        except Exception as e:
            return Observation(
                step_id=step.step_id,
                tool_name=step.action,
                success=False,
                error=str(e),
            )

    def _validate_document(self, document_path: str, document_type: Optional[str], iteration: int) -> SelfCheckResult:
        """Validate a generated document."""
        errors = []
        
        try:
            path = self.filesystem_jail._resolve_and_validate(document_path)
            
            if not path.exists():
                return SelfCheckResult(
                    valid=False,
                    errors=[ValidationError(
                        field="document",
                        issue=f"Document not found: {document_path}",
                        severity=ValidationSeverity.CRITICAL,
                    )],
                    iteration=iteration,
                    document_path=document_path,
                    document_type=document_type,
                )
            
            if document_type == "docx" or document_path.endswith(".docx"):
                from docx import Document
                try:
                    doc = Document(str(path))
                    if not doc.paragraphs:
                        errors.append(ValidationError(
                            field="content",
                            issue="Document has no paragraphs",
                            severity=ValidationSeverity.CRITICAL,
                        ))
                except Exception as e:
                    errors.append(ValidationError(
                        field="format",
                        issue=f"Invalid DOCX format: {e}",
                        severity=ValidationSeverity.CRITICAL,
                    ))
            
            elif document_type == "xlsx" or document_path.endswith(".xlsx"):
                from openpyxl import load_workbook
                try:
                    wb = load_workbook(str(path))
                    if not wb.sheetnames:
                        errors.append(ValidationError(
                            field="sheets",
                            issue="Workbook has no sheets",
                            severity=ValidationSeverity.CRITICAL,
                        ))
                except Exception as e:
                    errors.append(ValidationError(
                        field="format",
                        issue=f"Invalid XLSX format: {e}",
                        severity=ValidationSeverity.CRITICAL,
                    ))
            
            return SelfCheckResult(
                valid=len(errors) == 0,
                errors=errors,
                iteration=iteration,
                document_path=document_path,
                document_type=document_type,
            )
        
        except Exception as e:
            return SelfCheckResult(
                valid=False,
                errors=[ValidationError(
                    field="validation",
                    issue=f"Validation error: {e}",
                    severity=ValidationSeverity.CRITICAL,
                )],
                iteration=iteration,
                document_path=document_path,
                document_type=document_type,
            )