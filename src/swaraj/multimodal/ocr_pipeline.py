"""SWARAJ Multimodal OCR Pipeline.

Supports local ONNX-based RapidOCR and PaddleOCR backends with PyMuPDF image extraction.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import time
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
    """Multi-backend OCR engine (RapidOCR ONNX + PaddleOCR fallback)."""

    def __init__(self):
        self._backend = None
        self._available = False
        self._ocr = None

        # Try RapidOCR (preferred: pure ONNX, zero external system dependencies)
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR()
            self._backend = "rapidocr"
            self._available = True
            return
        except Exception:
            pass

        # Try PaddleOCR fallback
        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            self._backend = "paddleocr"
            self._available = True
            return
        except Exception:
            self._ocr = None

    @property
    def available(self) -> bool:
        return self._available

    def process_pdf(self, pdf_path: str, max_pages: int = 20) -> OCRResult:
        """Process a PDF file and return OCR results."""
        if not self._available:
            raise RuntimeError(
                "No OCR backend available. Install rapidocr-onnxruntime or paddleocr."
            )

        start_time = time.time()
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        blocks: List[TextBlock] = []
        full_text_parts: List[str] = []
        pages_count = 0

        # Extract images from PDF using PyMuPDF (fast, self-contained)
        try:
            import pymupdf
            doc = pymupdf.open(str(pdf_file))
            pages_count = min(len(doc), max_pages)

            for page_num in range(pages_count):
                page = doc[page_num]
                # Render page at 150 DPI for clean OCR
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")

                if self._backend == "rapidocr":
                    result, _ = self._ocr(img_bytes)
                    if result:
                        for item in result:
                            # RapidOCR returns [[bbox], text, score]
                            bbox = item[0] if len(item) > 0 else None
                            text = str(item[1]).strip() if len(item) > 1 else ""
                            conf = float(item[2]) if len(item) > 2 else 1.0
                            if text:
                                blocks.append(TextBlock(
                                    text=text,
                                    page=page_num + 1,
                                    bbox=[float(x) for x in bbox[0]] if bbox and len(bbox) > 0 else None,
                                    confidence=conf,
                                ))
                                full_text_parts.append(text)
                elif self._backend == "paddleocr":
                    import numpy as np
                    from PIL import Image
                    import io
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    result = self._ocr.ocr(np.array(img, dtype=np.uint8), cls=True)
                    if result and result[0]:
                        for line in result[0]:
                            text = line[1][0] if len(line) > 1 and len(line[1]) > 0 else ""
                            conf = line[1][1] if len(line) > 1 and len(line[1]) > 1 else None
                            if text:
                                blocks.append(TextBlock(
                                    text=text,
                                    page=page_num + 1,
                                    confidence=conf,
                                ))
                                full_text_parts.append(text)

        except Exception as e:
            # If PyMuPDF fails, try pdf2image as legacy fallback
            try:
                from pdf2image import convert_from_path
                import numpy as np
                images = convert_from_path(str(pdf_file), first_page=1, last_page=max_pages)
                pages_count = len(images)
                for page_num, image in enumerate(images, start=1):
                    img_arr = np.array(image.convert("RGB"), dtype=np.uint8)
                    if self._backend == "rapidocr":
                        result, _ = self._ocr(img_arr)
                        if result:
                            for item in result:
                                text = str(item[1]).strip() if len(item) > 1 else ""
                                if text:
                                    blocks.append(TextBlock(text=text, page=page_num, confidence=float(item[2])))
                                    full_text_parts.append(text)
            except Exception as inner_e:
                raise RuntimeError(f"OCR processing failed: {e} | Fallback failed: {inner_e}")

        processing_time = (time.time() - start_time) * 1000

        return OCRResult(
            filename=pdf_file.name,
            pages=pages_count,
            blocks=blocks,
            full_text="\n".join(full_text_parts),
            processing_time_ms=processing_time,
            backend=self._backend,
        )
