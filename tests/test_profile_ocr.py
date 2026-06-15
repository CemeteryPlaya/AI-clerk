from ai_clerk.profile.extraction.ocr import FakeOcrEngine, TesseractOcrEngine


def test_fake_ocr_returns_text_and_counts_calls():
    engine = FakeOcrEngine(text="распознанный текст")
    assert engine.recognize_pdf(b"%PDF-fake") == "распознанный текст"
    assert engine.calls == 1


def test_tesseract_engine_constructs_without_native_deps():
    # Heavy deps (poppler/tesseract) are imported lazily inside recognize_pdf,
    # so constructing the adapter must not require them.
    engine = TesseractOcrEngine(dpi=200)
    assert engine is not None
