from typing import Protocol


class OcrEngine(Protocol):
    def recognize_pdf(self, pdf_bytes: bytes, langs: str = "rus+kaz+eng") -> str: ...


class FakeOcrEngine:
    """Test double: returns canned text and records call count."""

    def __init__(self, text: str = ""):
        self.text = text
        self.calls = 0

    def recognize_pdf(self, pdf_bytes: bytes, langs: str = "rus+kaz+eng") -> str:
        self.calls += 1
        return self.text


class TesseractOcrEngine:
    """Production OCR: rasterize PDF pages (poppler) and run Tesseract.

    poppler + tesseract are imported lazily so this module loads on machines
    without those native dependencies (e.g. the Windows dev box). Real OCR is
    exercised in Docker (see the OCR system-deps task).
    """

    def __init__(self, dpi: int = 300):
        self._dpi = dpi

    def recognize_pdf(self, pdf_bytes: bytes, langs: str = "rus+kaz+eng") -> str:
        from pdf2image import convert_from_bytes
        from pytesseract import image_to_string

        images = convert_from_bytes(pdf_bytes, dpi=self._dpi)
        return "\n".join(image_to_string(image, lang=langs) for image in images)
