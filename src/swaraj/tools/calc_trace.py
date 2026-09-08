"""Calculation Trace Tool - Records numeric transformations with source references."""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel


class TraceEntry(BaseModel):
    """Single calculation trace entry."""
    entry_id: str
    timestamp: str
    operation: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    source_references: List[str]
    verified: bool = False
    notes: Optional[str] = None


class CalculationTrace:
    """Maintains a trace of numeric transformations for validation."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.entries: List[TraceEntry] = []
        self._counter = 0
    
    def record(
        self,
        operation: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        source_references: Optional[List[str]] = None,
        verified: bool = False,
        notes: Optional[str] = None,
    ) -> TraceEntry:
        """Record a calculation step."""
        self._counter += 1
        
        entry = TraceEntry(
            entry_id=f"{self.run_id}-calc-{self._counter:04d}",
            timestamp=datetime.utcnow().isoformat(),
            operation=operation,
            inputs=inputs,
            outputs=outputs,
            source_references=source_references or [],
            verified=verified,
            notes=notes,
        )
        
        self.entries.append(entry)
        return entry
    
    def validate_numeric_consistency(self) -> tuple[bool, List[str]]:
        """Validate numeric consistency across trace entries."""
        errors = []
        
        for entry in self.entries:
            if not entry.source_references:
                errors.append(
                    f"Entry {entry.entry_id}: No source references for numeric values"
                )
            
            if entry.verified and not entry.source_references:
                errors.append(
                    f"Entry {entry.entry_id}: Marked verified but has no source references"
                )
        
        return len(errors) == 0, errors
    
    def get_unverified_entries(self) -> List[TraceEntry]:
        """Return entries that lack verification."""
        return [e for e in self.entries if not e.verified]
    
    def to_dict(self) -> Dict[str, Any]:
        """Export trace as dictionary."""
        return {
            "run_id": self.run_id,
            "entry_count": len(self.entries),
            "entries": [e.dict() for e in self.entries],
        }
