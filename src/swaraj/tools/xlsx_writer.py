"""XLSX Writer with filesystem jail validation."""

from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime


class XLSXWriter:
    """Generate Excel spreadsheets with structured data for self-check."""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
    
    def write(
        self,
        filename: str,
        sheet_name: str = "Data",
        data: Optional[List[List[Union[str, int, float]]]] = None,
        headers: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write an XLSX file and return the full path."""
        from openpyxl import Workbook
        
        safe_path = self.workspace_root / "output" / filename
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name
        
        if headers:
            ws.append(headers)
        
        if data:
            for row in data:
                ws.append(row)
        else:
            ws.append(["Generated", datetime.utcnow().isoformat()])
            ws.append(["Sheet", sheet_name])
            if metadata:
                for key, value in metadata.items():
                    ws.append([key, str(value)])
        
        wb.save(str(safe_path))
        
        return str(safe_path)
    
    def validate(self, filepath: str) -> tuple[bool, List[str]]:
        """Validate an XLSX file structure."""
        from openpyxl import load_workbook
        
        errors = []
        
        try:
            wb = load_workbook(filepath)
            
            if not wb.sheetnames:
                errors.append("Workbook has no sheets")
            
            ws = wb.active
            if ws.max_row == 0:
                errors.append("Active sheet has no rows")
            
            return len(errors) == 0, errors
        
        except Exception as e:
            return False, [f"Validation error: {e}"]
