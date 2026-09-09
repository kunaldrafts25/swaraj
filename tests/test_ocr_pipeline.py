"""Tests for SWARAJ OCR Pipeline."""

import pytest
from pathlib import Path
from swaraj.multimodal.ocr_pipeline import OCREngine, TextBlock, OCRResult


def test_ocr_engine_init():
    """Verify OCREngine initializes without uncaught exceptions."""
    engine = OCREngine()
    assert isinstance(engine.available, bool)


def test_ocr_data_models():
    """Verify OCR data models."""
    block = TextBlock(text="Inspection Report", page=1, confidence=0.98)
    assert block.text == "Inspection Report"
    assert block.page == 1

    res = OCRResult(
        filename="test.pdf",
        pages=1,
        blocks=[block],
        full_text="Inspection Report",
        processing_time_ms=120.0,
        backend="paddleocr",
    )
    assert res.pages == 1
    assert "Inspection" in res.full_text


@pytest.mark.skipif(not OCREngine().available, reason="PaddleOCR not installed in current environment")
def test_ocr_process_pdf(tmp_path):
    """Verify OCR processing on a synthetic single-page PDF."""
    engine = OCREngine()
    
    # Generate a simple PDF if reportlab/fpdf is available
    pdf_path = tmp_path / "sample.pdf"
    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf_path))
        c.drawString(100, 750, "VALVE INSPECTION REPORT PASS")
        c.save()
    except ImportError:
        pytest.skip("reportlab not available to generate test PDF")

    result = engine.process_pdf(str(pdf_path))
    assert result.pages >= 1
    assert len(result.blocks) > 0
    assert "VALVE" in result.full_text.upper() or "INSPECTION" in result.full_text.upper()
