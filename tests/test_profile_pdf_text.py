import io

from reportlab.pdfgen import canvas

from ai_clerk.profile.extraction.ocr import FakeOcrEngine
from ai_clerk.profile.extraction.pdf_text import PdfTextExtractor


def _pdf_with_text(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.save()
    return buf.getvalue()


def _blank_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.showPage()  # a page with no text layer
    c.save()
    return buf.getvalue()


def test_uses_text_layer_when_present():
    ocr = FakeOcrEngine(text="OCR-FALLBACK")
    extractor = PdfTextExtractor(ocr)
    # ASCII so reportlab's default font renders it (Cyrillic would become
    # replacement glyphs in this fixture); >= the 20-char text-layer threshold.
    out = extractor.extract_text(_pdf_with_text("Passport 900101300123 issued"))
    assert "900101300123" in out
    assert ocr.calls == 0  # text layer made OCR unnecessary


def test_falls_back_to_ocr_when_no_text_layer():
    ocr = FakeOcrEngine(text="OCR-FALLBACK TEXT")
    extractor = PdfTextExtractor(ocr)
    out = extractor.extract_text(_blank_pdf())
    assert out == "OCR-FALLBACK TEXT"
    assert ocr.calls == 1
