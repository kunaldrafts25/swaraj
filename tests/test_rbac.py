"""Tests for SWARAJ RBAC - Deny-by-default authorization."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from swaraj.governance.rbac import (
    Role,
    PermissionResult,
    ApprovalRequest,
    RBACManager,
)


@pytest.fixture
def temp_policy_file(tmp_path):
    """Create temporary RBAC policy file."""
    policy = {
        "version": "1.0.0",
        "default_action": "deny",
        "roles": {
            "Inspector": {
                "permissions": ["read_document", "view_audit_log"],
                "requires_approval": ["write_document"],
            },
            "Approver": {
                "permissions": ["read_document", "write_document", "approve_action"],
                "requires_approval": ["manage_users"],
            },
            "Admin": {
                "permissions": [
                    "read_document", "write_document", "approve_action",
                    "manage_users", "view_audit_log"
                ],
                "requires_approval": [],
            },
        },
    }
    
    policy_path = tmp_path / "rbac_policy.json"
    policy_path.write_text(json.dumps(policy))
    return policy_path


@pytest.fixture
def temp_users_file(tmp_path):
    """Create temporary users file."""
    users = {
        "users": [
            {"user_id": "inspector_user", "role": "Inspector"},
            {"user_id": "approver_user", "role": "Approver"},
            {"user_id": "admin_user", "role": "Admin"},
            {"user_id": "unknown_user", "role": "UnknownRole"},
        ]
    }
    
    users_path = tmp_path / "users.json"
    users_path.write_text(json.dumps(users))
    return users_path


@pytest.fixture
def rbac_manager(temp_policy_file, temp_users_file):
    """Create RBACManager with test fixtures."""
    return RBACManager(temp_policy_file, temp_users_file)


class TestDenyByDefault:
    """Test deny-by-default behavior."""
    
    def test_unknown_user_denied(self, rbac_manager):
        """Unknown users are denied by default."""
        result = rbac_manager.check_permission(
            "nonexistent_user",
            "read_document"
        )
        
        assert result.authorized is False
        assert "not found" in result.reason
    
    def test_action_not_in_permissions_denied(self, rbac_manager):
        """Actions not explicitly permitted are denied."""
        # Inspector can only read, not write
        result = rbac_manager.check_permission(
            "inspector_user",
            "write_document"
        )
        
        assert result.authorized is False
        assert "requires approval" in result.reason or "not permitted" in result.reason
    
    def test_dangerous_action_denied_by_default(self, rbac_manager):
        """Dangerous actions denied unless explicitly permitted."""
        # Inspector trying to manage users (not permitted)
        result = rbac_manager.check_permission(
            "inspector_user",
            "manage_users"
        )
        
        assert result.authorized is False


class TestRolePermissions:
    """Test role-specific permissions."""
    
    def test_inspector_can_read(self, rbac_manager):
        """Inspector can read documents."""
        result = rbac_manager.check_permission(
            "inspector_user",
            "read_document"
        )
        
        assert result.authorized is True
        assert result.role == "Inspector"
    
    def test_inspector_cannot_approve(self, rbac_manager):
        """Inspector cannot approve actions."""
        result = rbac_manager.check_permission(
            "inspector_user",
            "approve_action"
        )
        
        assert result.authorized is False
    
    def test_approver_can_write(self, rbac_manager):
        """Approver can write documents."""
        result = rbac_manager.check_permission(
            "approver_user",
            "write_document"
        )
        
        assert result.authorized is True
        assert result.role == "Approver"
    
    def test_approver_can_approve(self, rbac_manager):
        """Approver can approve actions."""
        result = rbac_manager.check_permission(
            "approver_user",
            "approve_action"
        )
        
        assert result.authorized is True
    
    def test_admin_has_full_access(self, rbac_manager):
        """Admin has all permissions."""
        actions = [
            "read_document",
            "write_document",
            "approve_action",
            "manage_users",
            "view_audit_log",
        ]
        
        for action in actions:
            result = rbac_manager.check_permission("admin_user", action)
            assert result.authorized is True, f"Admin should be able to {action}"


class TestApprovalQueue:
    """Test approval queue functionality."""
    
    def test_inspector_write_requires_approval(self, rbac_manager):
        """Inspector write action creates approval request."""
        result = rbac_manager.check_permission(
            "inspector_user",
            "write_document",
            "report.docx"
        )
        
        assert result.authorized is False
        assert result.approval_required is True
        assert result.approval_id is not None
        assert result.approval_id.startswith("APR-")
    
    def test_approval_request_stored(self, rbac_manager):
        """Approval requests are stored in queue."""
        result = rbac_manager.check_permission(
            "inspector_user",
            "write_document",
            "report.docx"
        )
        
        # Retrieve the request
        request = rbac_manager.get_approval_request(result.approval_id)
        
        assert request is not None
        assert request.user_id == "inspector_user"
        assert request.action == "write_document"
        assert request.status == "pending"
    
    def test_approver_can_approve_request(self, rbac_manager):
        """Approver can approve pending requests."""
        # Create approval request
        result = rbac_manager.check_permission(
            "inspector_user",
            "write_document"
        )
        
        # Approve it
        approved = rbac_manager.approve_request(
            result.approval_id,
            "approver_user",
            "Looks good"
        )
        
        assert approved is not None
        assert approved.status == "approved"
        assert approved.approver_id == "approver_user"
    
    def test_inspector_cannot_approve(self, rbac_manager):
        """Inspector cannot approve requests."""
        result = rbac_manager.check_permission(
            "inspector_user",
            "write_document"
        )
        
        with pytest.raises(PermissionError):
            rbac_manager.approve_request(
                result.approval_id,
                "inspector_user"
            )
    
    def test_admin_can_deny_request(self, rbac_manager):
        """Admin can deny requests."""
        result = rbac_manager.check_permission(
            "inspector_user",
            "write_document"
        )
        
        denied = rbac_manager.deny_request(
            result.approval_id,
            "admin_user",
            "Security concern"
        )
        
        assert denied is not None
        assert denied.status == "denied"


class TestPlanEvaluation:
    """Test planning-layer RBAC evaluation."""
    
    def test_plan_with_mixed_permissions(self, rbac_manager):
        """Plan evaluation prunes unauthorized steps."""
        planned_steps = [
            {"action": "read_document", "resource": "report.pdf"},
            {"action": "write_document", "resource": "output.docx"},
            {"action": "manage_users", "resource": "users.json"},
        ]
        
        executable, denials = rbac_manager.evaluate_plan(
            "inspector_user",
            planned_steps
        )
        
        # Only read should be executable
        assert len(executable) == 1
        assert executable[0]["action"] == "read_document"
        
        # Two denials (write requires approval, manage_users denied)
        assert len(denials) == 2
    
    def test_denial_record_contains_reason(self, rbac_manager):
        """Denial records include structured reason."""
        planned_steps = [
            {"action": "manage_users", "resource": "users.json"},
        ]
        
        _, denials = rbac_manager.evaluate_plan(
            "inspector_user",
            planned_steps
        )
        
        assert len(denials) > 0
        denial = denials[0]
        
        assert "permission_result" in denial
        assert denial["permission_result"]["authorized"] is False
        assert "reason" in denial["permission_result"]


class TestStructuredDenial:
    """Test structured denial records."""
    
    def test_denial_has_all_fields(self, rbac_manager):
        """Denial records have all required fields."""
        result = rbac_manager.check_permission(
            "inspector_user",
            "manage_users"
        )
        
        assert hasattr(result, 'authorized')
        assert hasattr(result, 'role')
        assert hasattr(result, 'action')
        assert hasattr(result, 'reason')
        assert hasattr(result, 'approval_required')
    
    def test_denial_serializable(self, rbac_manager):
        """Denial records can be serialized to JSON."""
        result = rbac_manager.check_permission(
            "inspector_user",
            "manage_users"
        )
        
        # Should be able to convert to dict
        data = result.model_dump()
        
        assert data["authorized"] is False
        assert data["role"] == "Inspector"
        assert data["action"] == "manage_users"
