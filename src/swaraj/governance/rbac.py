"""
SWARAJ RBAC - Role-Based Access Control at the Planning Layer.

Implements deny-by-default authorization where every planned action
is evaluated BEFORE execution. Prohibited actions are pruned;
approval-required actions route to human approval queue.
"""

import json
import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class Role(str, Enum):
    """Pilot roles with explicit permissions."""
    INSPECTOR = "Inspector"
    APPROVER = "Approver"
    ADMIN = "Admin"


class Action(str, Enum):
    """Actions that can be authorized or denied."""
    READ_DOCUMENT = "read_document"
    WRITE_DOCUMENT = "write_document"
    EXECUTE_TOOL = "execute_tool"
    APPROVE_ACTION = "approve_action"
    MANAGE_USERS = "manage_users"
    VIEW_AUDIT_LOG = "view_audit_log"
    GENERATE_CERTIFICATE = "generate_certificate"


class PermissionResult(BaseModel):
    """Result of a permission check."""
    authorized: bool
    role: str
    action: str
    reason: str
    approval_required: bool = False
    approval_id: Optional[str] = None
    
    class Config:
        frozen = True


class ApprovalRequest(BaseModel):
    """Request awaiting human approval."""
    approval_id: str
    user_id: str
    role: str
    action: str
    resource: str
    requested_at: str
    status: str = "pending"  # pending, approved, denied
    approver_id: Optional[str] = None
    decided_at: Optional[str] = None
    decision_reason: Optional[str] = None
    
    class Config:
        frozen = False


class RBACManager:
    """
    Deny-by-default RBAC manager operating at planning layer.
    
    SECURITY BOUNDARY: All actions must be checked BEFORE execution.
    Never check permissions after an action has already executed.
    """
    
    def __init__(self, policy_path: Path, users_path: Path):
        self.policy_path = policy_path
        self.users_path = users_path
        self._policy: dict = {}
        self._users: dict = {}
        self._approval_queue: dict[str, ApprovalRequest] = {}
        self._load_policy()
        self._load_users()
    
    def _load_policy(self) -> None:
        """Load RBAC policy from JSON file."""
        if not self.policy_path.exists():
            raise FileNotFoundError(f"RBAC policy not found: {self.policy_path}")
        
        with open(self.policy_path, 'r') as f:
            self._policy = json.load(f)
    
    def _load_users(self) -> None:
        """Load users from JSON file."""
        if not self.users_path.exists():
            raise FileNotFoundError(f"Users file not found: {self.users_path}")
        
        with open(self.users_path, 'r') as f:
            users_data = json.load(f)
            self._users = {u["user_id"]: u for u in users_data.get("users", [])}
    
    def get_user_role(self, user_id: str) -> Optional[Role]:
        """Get role for a user. Returns None if user not found."""
        user = self._users.get(user_id)
        if not user:
            return None
        try:
            return Role(user.get("role"))
        except (ValueError, TypeError):
            return None
    
    def check_permission(
        self,
        user_id: str,
        action: str,
        resource: str = "",
    ) -> PermissionResult:
        """
        Check if user can perform action on resource.
        
        DENY-BY-DEFAULT: If action not explicitly permitted for role, deny.
        
        Args:
            user_id: User identifier
            action: Action to perform
            resource: Resource being accessed
        
        Returns:
            PermissionResult with authorization decision
        """
        role = self.get_user_role(user_id)
        if role is None:
            return PermissionResult(
                authorized=False,
                role="unknown",
                action=action,
                reason=f"User '{user_id}' not found",
            )
        
        role_name = role.value
        role_config = self._policy.get("roles", {}).get(role_name, {})
        
        # Check if action is explicitly permitted for this role
        permitted_actions = role_config.get("permissions", [])
        
        if action not in permitted_actions:
            # Action not permitted - check if it requires approval
            approval_actions = role_config.get("requires_approval", [])
            
            if action in approval_actions:
                # Create approval request
                approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
                approval_request = ApprovalRequest(
                    approval_id=approval_id,
                    user_id=user_id,
                    role=role_name,
                    action=action,
                    resource=resource,
                    requested_at=datetime.now(timezone.utc).isoformat(),
                )
                self._approval_queue[approval_id] = approval_request
                
                return PermissionResult(
                    authorized=False,
                    role=role_name,
                    action=action,
                    reason=f"Action '{action}' requires approval for role '{role_name}'",
                    approval_required=True,
                    approval_id=approval_id,
                )
            
            # Denied by default
            return PermissionResult(
                authorized=False,
                role=role_name,
                action=action,
                reason=f"Action '{action}' not permitted for role '{role_name}'",
            )
        
        # Explicitly permitted
        return PermissionResult(
            authorized=True,
            role=role_name,
            action=action,
            reason=f"Action '{action}' permitted for role '{role_name}'",
        )
    
    def evaluate_plan(self, user_id: str, planned_steps: list[dict]) -> tuple[list[dict], list[PermissionResult]]:
        """
        Evaluate entire agent plan before execution.
        
        SECURITY BOUNDARY: This must be called BEFORE any step executes.
        Prunes prohibited steps and routes approval-required steps to queue.
        
        Args:
            user_id: User executing the plan
            planned_steps: List of planned actions with 'action' and 'resource' keys
        
        Returns:
            Tuple of (executable_steps, denial_records)
        """
        executable_steps = []
        denial_records = []
        
        for step in planned_steps:
            action = step.get("action", "")
            resource = step.get("resource", "")
            
            result = self.check_permission(user_id, action, resource)
            
            if result.authorized:
                executable_steps.append(step)
            else:
                denial_record = {
                    "step": step,
                    "permission_result": result.model_dump(),
                    "pruned": not result.approval_required,
                    "approval_pending": result.approval_required,
                }
                denial_records.append(denial_record)
        
        return executable_steps, denial_records
    
    def get_approval_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by ID."""
        return self._approval_queue.get(approval_id)
    
    def approve_request(
        self,
        approval_id: str,
        approver_id: str,
        reason: str = "",
    ) -> Optional[ApprovalRequest]:
        """
        Approve a pending request.
        
        Args:
            approval_id: Approval request ID
            approver_id: User approving the request
            reason: Reason for approval
        
        Returns:
            Updated ApprovalRequest or None if not found
        """
        request = self._approval_queue.get(approval_id)
        if not request:
            return None
        
        # Verify approver has permission
        approver_role = self.get_user_role(approver_id)
        if approver_role not in [Role.APPROVER, Role.ADMIN]:
            raise PermissionError(f"User '{approver_id}' cannot approve requests")
        
        now = datetime.now(timezone.utc).isoformat()
        request.status = "approved"
        request.approver_id = approver_id
        request.decided_at = now
        request.decision_reason = reason
        
        return request
    
    def deny_request(
        self,
        approval_id: str,
        approver_id: str,
        reason: str = "",
    ) -> Optional[ApprovalRequest]:
        """
        Deny a pending request.
        
        Args:
            approval_id: Approval request ID
            approver_id: User denying the request
            reason: Reason for denial
        
        Returns:
            Updated ApprovalRequest or None if not found
        """
        request = self._approval_queue.get(approval_id)
        if not request:
            return None
        
        approver_role = self.get_user_role(approver_id)
        if approver_role not in [Role.APPROVER, Role.ADMIN]:
            raise PermissionError(f"User '{approver_id}' cannot deny requests")
        
        now = datetime.now(timezone.utc).isoformat()
        request.status = "denied"
        request.approver_id = approver_id
        request.decided_at = now
        request.decision_reason = reason
        
        return request
    
    def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return [r for r in self._approval_queue.values() if r.status == "pending"]

    def get_approval_queue(self) -> list[ApprovalRequest]:
        """Get pending approval queue items."""
        return self.get_pending_approvals()

    def process_approval(
        self,
        approval_id: str,
        approved: bool,
        reviewer_id: str,
        comments: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """Process an approval or rejection decision."""
        if approved:
            return self.approve_request(approval_id=approval_id, approver_id=reviewer_id, reason=comments or "")
        else:
            return self.deny_request(approval_id=approval_id, approver_id=reviewer_id, reason=comments or "")

    def evaluate_action(
        self,
        action: str | Action,
        user_id: str,
        role: Optional[str] = None,
        artifact: str = "",
    ) -> PermissionResult:
        """
        Evaluate a single action with optional role fallback.
        """
        action_str = action.value if isinstance(action, Action) else str(action)
        
        # Determine role: check stored role first, fallback to passed role
        user_role = self.get_user_role(user_id)
        if user_role is None and role:
            try:
                # Handle case-insensitivity: "inspector" -> "Inspector"
                normalized_role = role.strip().title()
                if normalized_role == "Operator":
                    normalized_role = "Inspector"  # Map Operator to Inspector permissions
                user_role = Role(normalized_role)
            except Exception:
                # Fallback check
                for r in Role:
                    if r.value.lower() == role.lower():
                        user_role = r
                        break

        if user_role is None:
            return PermissionResult(
                authorized=False,
                role="unknown",
                action=action_str,
                reason=f"User '{user_id}' not found and role '{role}' is invalid",
            )

        role_name = user_role.value
        role_config = self._policy.get("roles", {}).get(role_name, {})
        permitted_actions = role_config.get("permissions", [])

        if action_str not in permitted_actions:
            approval_actions = role_config.get("requires_approval", [])
            if action_str in approval_actions:
                approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
                approval_request = ApprovalRequest(
                    approval_id=approval_id,
                    user_id=user_id,
                    role=role_name,
                    action=action_str,
                    resource=artifact,
                    requested_at=datetime.now(timezone.utc).isoformat(),
                )
                self._approval_queue[approval_id] = approval_request
                return PermissionResult(
                    authorized=False,
                    role=role_name,
                    action=action_str,
                    reason=f"Action '{action_str}' requires approval for role '{role_name}'",
                    approval_required=True,
                    approval_id=approval_id,
                )

            return PermissionResult(
                authorized=False,
                role=role_name,
                action=action_str,
                reason=f"Action '{action_str}' not permitted for role '{role_name}'",
            )

        return PermissionResult(
            authorized=True,
            role=role_name,
            action=action_str,
            reason=f"Action '{action_str}' permitted for role '{role_name}'",
        )

