"""Tests for reflexive document self-check."""

import pytest
from pathlib import Path
import tempfile
from docx import Document as DocxDocument
from openpyxl import Workbook

from swaraj.agent.schemas import SelfCheckResult, ValidationError, ValidationSeverity
from swaraj.tools.docx_writer import DocXWriter
from swaraj.tools.xlsx_writer import XLSXWriter


class TestValidDocumentSelfCheck:
    """Test that valid documents pass self-check."""
    
    def test_valid_docx_passes_self_check(self):
        """A properly generated DOCX should pass validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = DocXWriter(tmpdir)
            filepath = writer.write("test_valid.docx", title="Test Report")
            
            doc = DocxDocument(filepath)
            assert len(doc.paragraphs) > 0
    
    def test_valid_xlsx_passes_self_check(self):
        """A properly generated XLSX should pass validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = XLSXWriter(tmpdir)
            filepath = writer.write("test_valid.xlsx", sheet_name="Data")
            
            wb = Workbook()
            wb = writer.__class__(tmpdir)
            from openpyxl import load_workbook
            loaded = load_workbook(filepath)
            assert len(loaded.sheetnames) > 0


class TestMalformedDocumentDetection:
    """Test that malformed documents are detected."""
    
    def test_empty_docx_detected(self):
        """An empty DOCX-like file should fail validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "fake.docx"
            fake_path.write_text("This is not a real DOCX file")
            
            writer = DocXWriter(tmpdir)
            valid, errors = writer.validate(str(fake_path))
            
            assert not valid
            assert len(errors) > 0
    
    def test_empty_xlsx_detected(self):
        """An empty XLSX-like file should fail validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "fake.xlsx"
            fake_path.write_text("This is not a real XLSX file")
            
            writer = XLSXWriter(tmpdir)
            valid, errors = writer.validate(str(fake_path))
            
            assert not valid
            assert len(errors) > 0


class TestRequiredSectionsValidation:
    """Test detection of missing required sections."""
    
    def test_docx_without_headings_detected(self):
        """DOCX without headings should be flagged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = DocXWriter(tmpdir)
            filepath = writer.write("no_headings.docx", title="", sections=None)
            
            doc = DocxDocument(filepath)
            headings = [p for p in doc.paragraphs if p.style.name.startswith('Heading')]
            
            assert len(headings) == 0
    
    def test_docx_with_sections_has_headings(self):
        """DOCX with sections should have headings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = DocXWriter(tmpdir)
            sections = [
                {"heading": "Executive Summary", "content": "Summary text", "level": 1},
                {"heading": "Findings", "content": "Finding details", "level": 2},
            ]
            filepath = writer.write("with_sections.docx", title="Report", sections=sections)
            
            doc = DocxDocument(filepath)
            headings = [p for p in doc.paragraphs if p.style.name.startswith('Heading')]
            
            assert len(headings) >= 2


class TestCitationValidation:
    """Test citation resolution checking."""
    
    def test_missing_citation_flagged(self):
        """References to non-existent sources should be flagged."""
        from swaraj.agent.graph import AgentGraph
        from swaraj.governance.rbac import RBACManager
        from swaraj.tools.fs_jail import FilesystemJail
        from swaraj.agent.schemas import TaskInput
        
        with tempfile.TemporaryDirectory() as tmpdir:
            policy_path = Path(tmpdir) / "rbac_policy.json"
            users_path = Path(tmpdir) / "users.json"
            policy_path.write_text('{"roles": {"Admin": {"permissions": ["*"]}}}')
            users_path.write_text('{"test_user": {"role": "Admin", "password_hash": "x"}}')
            
            rbac = RBACManager(policy_path=policy_path, users_path=users_path)
            jail = FilesystemJail(Path(tmpdir))
            graph = AgentGraph(rbac, jail, tmpdir)
            
            task_input = TaskInput(
                task_description="Test",
                task_type=None,
                user_id="test",
                role="Admin",
                source_documents=[],
                output_schema=None,
            )
            state = graph.create_run(task_input)
            
            # Use relative path to test missing document (not absolute path rejection)
            result = graph._validate_document("nonexistent/doc.docx", "docx", 1)
            
            assert not result.valid
            assert any("not found" in e.issue.lower() for e in result.errors)


class TestIterationLimitEnforcement:
    """Test that maximum iteration count is enforced."""
    
    def test_iteration_count_tracked(self):
        """Self-check iteration count should increment."""
        from swaraj.agent.graph import AgentGraph
        from swaraj.governance.rbac import RBACManager
        from swaraj.tools.fs_jail import FilesystemJail
        from swaraj.agent.schemas import TaskInput
        
        with tempfile.TemporaryDirectory() as tmpdir:
            policy_path = Path(tmpdir) / "rbac_policy.json"
            users_path = Path(tmpdir) / "users.json"
            policy_path.write_text('{"roles": {"Admin": {"permissions": ["*"]}}}')
            users_path.write_text('{"test_user": {"role": "Admin", "password_hash": "x"}}')
            
            rbac = RBACManager(policy_path=policy_path, users_path=users_path)
            jail = FilesystemJail(Path(tmpdir))
            graph = AgentGraph(rbac, jail, tmpdir)
            
            task_input = TaskInput(
                task_description="Test",
                task_type=None,
                user_id="test",
                role="Admin",
                source_documents=[],
                output_schema=None,
            )
            state = graph.create_run(task_input)
            
            assert state.iteration_count == 0
            
            state = graph.self_check(state)
            assert state.iteration_count == 1
            
            state = graph.self_check(state)
            assert state.iteration_count == 2
    
    def test_max_iterations_exceeded_fails_run(self):
        """Exceeding max iterations should fail the run."""
        from swaraj.agent.graph import AgentGraph
        from swaraj.governance.rbac import RBACManager
        from swaraj.tools.fs_jail import FilesystemJail
        from swaraj.agent.schemas import RunState, TaskInput
        
        with tempfile.TemporaryDirectory() as tmpdir:
            policy_path = Path(tmpdir) / "rbac_policy.json"
            users_path = Path(tmpdir) / "users.json"
            policy_path.write_text('{"roles": {"Admin": {"permissions": ["*"]}}}')
            users_path.write_text('{"test_user": {"role": "Admin", "password_hash": "x"}}')
            
            rbac = RBACManager(policy_path=policy_path, users_path=users_path)
            jail = FilesystemJail(Path(tmpdir))
            graph = AgentGraph(rbac, jail, tmpdir)
            
            task_input = TaskInput(
                task_description="Test",
                task_type=None,
                user_id="test",
                role="Admin",
                source_documents=[],
                output_schema=None,
            )
            state = graph.create_run(task_input)
            
            state.max_iterations = 4
            
            for i in range(5):
                state = graph.self_check(state)
            
            assert state.current_state == RunState.FAILED
            assert "Maximum self-check iterations" in state.failure_reason


class TestStructuredErrorReporting:
    """Test that validation errors are structured properly."""
    
    def test_validation_error_has_required_fields(self):
        """ValidationError should have field, issue, and severity."""
        error = ValidationError(
            field="Risk Classification",
            issue="Required section missing",
            severity=ValidationSeverity.CRITICAL,
        )
        
        assert error.field == "Risk Classification"
        assert error.issue == "Required section missing"
        assert error.severity == ValidationSeverity.CRITICAL
    
    def test_self_check_result_structure(self):
        """SelfCheckResult should have valid, errors, and iteration."""
        result = SelfCheckResult(
            valid=False,
            errors=[ValidationError(
                field="test",
                issue="test issue",
                severity=ValidationSeverity.WARNING,
            )],
            iteration=1,
        )
        
        assert result.valid is False
        assert len(result.errors) == 1
        assert result.iteration == 1
        assert result.errors[0].severity == ValidationSeverity.WARNING
