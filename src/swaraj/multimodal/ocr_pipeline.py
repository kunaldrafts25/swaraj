"""SWARAJ Multimodal OCR Pipeline."""

from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class TextBlock(BaseModel):
    """OCR text block with location metadata."""
    text: str
    page: int
    bbox: Optional[List[float]] = None
    confidence: Optional[float] = None


class OCRResult(BaseModel):
    """Complete OCR result for a document."""
    filename: str
    pages: int
    blocks: List[TextBlock]
    full_text: str
    processing_time_ms: float
    backend: str


class OCREngine:
    """OCR engine using PaddleOCR."""
    
    def __init__(self):
        self._backend = None
        self._available = False
        
        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
            self._backend = "paddleocr"
            self._available = True
        except ImportError:
            self._ocr = None
    
    @property
    def available(self) -> bool:
        return self._available
    
    def process_pdf(self, pdf_path: str) -> OCRResult:
        """Process a PDF file and return OCR results."""
        if not self._available:
            raise RuntimeError(
                "PaddleOCR is not available. Cannot process documents. "
                "Install paddlepaddle and paddleocr packages."
            )
        
        import time
        start_time = time.time()
        
        try:
            from pdf2image import convert_from_path
            from PIL import Image
            
            pdf_file = Path(pdf_path)
            if not pdf_file.exists():
                raise FileNotFoundError(f"PDF not found: {pdf_path}")
            
            images = convert_from_path(str(pdf_file))
            blocks = []
            full_text_parts = []
            
            for page_num, image in enumerate(images, start=1):
                image_array = list(image.getdata())
                result = self._ocr.ocr(image_array, cls=True)
                
                if result and result[0]:
                    for line in result[0]:
                        bbox = line[0] if len(line) > 0 else None
                        text = line[1][0] if len(line) > 1 and len(line[1]) > 0 else ""
                        confidence = line[1][1] if len(line) > 1 and len(line[1]) > 1 else None
                        
                        blocks.append(TextBlock(
                            text=text,
                            page=page_num,
                            bbox=bbox,
                            confidence=confidence,
                        ))
                        full_text_parts.append(text)
            
            processing_time = (time.time() - start_time) * 1000
            
            return OCRResult(
                filename=pdf_file.name,
                pages=len(images),
                blocks=blocks,
                full_text="\n".join(full_text_parts),
                processing_time_ms=processing_time,
                backend=self._backend,
            )
        
        except ImportError as e:
            raise RuntimeError(
                f"Required dependency missing: {e}. "
                "Install pdf2image, Pillow, and poppler-utils."
            )
        except Exception as e:
            raise RuntimeError(f"OCR processing failed: {e}")
