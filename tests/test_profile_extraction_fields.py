from ai_clerk.profile.extraction.fields import (
    ExtractedProfile,
    RegexProfileExtractor,
)

SAMPLE = """
Удостоверение личности Республики Казахстан
ФИО: ИВАНОВ ИВАН ИВАНОВИЧ
ИИН 900101300123
№ документа: N12345678
Дата рождения: 01.01.1990
Гражданство: KAZ
"""


def test_extracts_all_fields():
    result = RegexProfileExtractor().extract(SAMPLE)
    assert result == ExtractedProfile(
        full_name="ИВАНОВ ИВАН ИВАНОВИЧ",
        iin="900101300123",
        document_number="N12345678",
        birth_date="01.01.1990",
        document_type="udo",  # "Удостоверение личности" in the sample
    )


def test_detects_passport_document_type():
    assert RegexProfileExtractor().extract("Паспорт гражданина").document_type == "passport"


def test_missing_fields_are_none():
    result = RegexProfileExtractor().extract("просто текст без данных")
    assert result == ExtractedProfile()


def test_extracts_partial():
    result = RegexProfileExtractor().extract("ИИН 123456789012 и больше ничего")
    assert result.iin == "123456789012"
    assert result.full_name is None
    assert result.document_number is None
    assert result.birth_date is None


def test_extracts_iin_without_separator():
    # OCR often merges the label and value: "ИИН900101300123".
    result = RegexProfileExtractor().extract("ИИН900101300123")
    assert result.iin == "900101300123"
