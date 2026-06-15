import re
from dataclasses import dataclass
from typing import Protocol

# Digit-boundary lookarounds (not \b) so the IIN is found even when OCR merges
# the label with the value, e.g. "ИИН900101300123" (Cyrillic letter + digit
# share \w, so \b would not fire there).
_IIN_RE = re.compile(r"(?<!\d)(\d{12})(?!\d)")
# No semantic validation (month/day ranges); a KZ ID document contains one date.
_DATE_RE = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")
_DOC_RE = re.compile(r"\b(N\s?\d{6,9})\b", re.IGNORECASE)
# KZ identity documents store the name in all-caps; lower-case OCR output of a
# text-layer PDF will not match this pattern (acceptable for the MVP scope).
_NAME_RE = re.compile(
    r"(?:ФИО|Ф\.?\s?И\.?\s?О\.?)\s*[:\-]?\s*"
    r"([А-ЯЁ][А-ЯЁA-Z\-]+(?:\s+[А-ЯЁ][А-ЯЁA-Z\-]+){1,2})"
)


@dataclass
class ExtractedProfile:
    full_name: str | None = None
    iin: str | None = None
    document_number: str | None = None
    birth_date: str | None = None


class ProfileExtractor(Protocol):
    def extract(self, text: str) -> ExtractedProfile: ...


class RegexProfileExtractor:
    """Deterministic, offline extractor for KZ identity documents."""

    def extract(self, text: str) -> ExtractedProfile:
        return ExtractedProfile(
            full_name=self._first(_NAME_RE, text),
            iin=self._first(_IIN_RE, text),
            document_number=self._normalize_doc(self._first(_DOC_RE, text)),
            birth_date=self._first(_DATE_RE, text),
        )

    @staticmethod
    def _first(pattern: re.Pattern, text: str) -> str | None:
        match = pattern.search(text)
        return match.group(1).strip() if match else None

    @staticmethod
    def _normalize_doc(value: str | None) -> str | None:
        return value.replace(" ", "").upper() if value else None
