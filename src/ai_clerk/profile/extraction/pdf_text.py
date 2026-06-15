import io

import pypdf

from ai_clerk.profile.extraction.ocr import OcrEngine


class PdfTextExtractor:
    """Extracts text from a PDF: tries the embedded text layer first and falls
    back to OCR for scanned/image-only documents."""

    def __init__(self, ocr_engine: OcrEngine, min_text_len: int = 20):
        self._ocr = ocr_engine
        self._min_text_len = min_text_len

    def extract_text(self, pdf_bytes: bytes) -> str:
        # NOTE: pypdf raises EmptyFileError/PdfStreamError on empty or corrupt
        # input; hardening against malformed uploads is deferred (handled at the
        # bot layer in a later phase), not silently swallowed here.
        text = self._text_layer(pdf_bytes)
        if len(text.strip()) >= self._min_text_len:
            return text
        return self._ocr.recognize_pdf(pdf_bytes)

    @staticmethod
    def _text_layer(pdf_bytes: bytes) -> str:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
