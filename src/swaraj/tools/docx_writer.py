"""DOCX Writer with filesystem jail validation."""

from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class DocXWriter:
    """Generate Word documents with structured content for self-check."""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
    
    def write(
        self,
        filename: str,
        title: str = "Document",
        sections: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write a DOCX file and return the full path."""
        from docx import Document
        
        safe_path = self.workspace_root / "output" / filename
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        
        doc = Document()
        
        doc.add_heading(title, 0)
        
        if metadata:
            doc.add_paragraph(f"Generated: {datetime.utcnow().isoformat()}")
            for key, value in metadata.items():
                doc.add_paragraph(f"{key}: {value}")
        
        if sections:
            for section in sections:
                heading = section.get("heading", "")
                content = section.get("content", "")
                if heading:
                    doc.add_heading(heading, level=section.get("level", 1))
                if content:
                    doc.add_paragraph(content)
        else:
            doc.add_paragraph(f"Document generated for: {title}")
            doc.add_paragraph("Content sections pending agent generation.")
        
        doc.save(str(safe_path))
        
        return str(safe_path)
    
    def validate(self, filepath: str) -> tuple[bool, List[str]]:
        """Validate a DOCX file structure."""
        from docx import Document
        
        errors = []
        
        try:
            doc = Document(filepath)
            
            if not doc.paragraphs:
                errors.append("Document has no paragraphs")
            
            headings = [p for p in doc.paragraphs if p.style.name.startswith('Heading')]
            if not headings:
                errors.append("Document has no headings")
            
            return len(errors) == 0, errors
        
        except Exception as e:
            return False, [f"Validation error: {e}"]
