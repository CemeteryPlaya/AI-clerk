# Phase 2 — Profile & Location — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an encrypted traveler `Profile` (PII ingested locally from an uploaded PDF via a text-layer-first / OCR-fallback pipeline) and an offline `LocationService` (bundled airports dataset → nearest airport + departure-point resolver), wired into the bot.

**Architecture:** Modular monolith (Python 3.14 + aiogram 3.x), following Phase 1 patterns: small pure-logic modules with a thin aiogram glue layer, async SQLAlchemy 2.0 (SQLite for tests, PostgreSQL in prod), Fernet `Cipher` for PII at rest. PDF text extraction, OCR, and field extraction each sit behind a swappable interface so unit tests run fully offline (a `FakeOcrEngine` + a deterministic `RegexProfileExtractor`); real Tesseract OCR is a production adapter verified in Docker. Location uses a bundled OurAirports-format CSV (no live geocoder).

**Tech Stack:** SQLAlchemy 2.0 async, cryptography (Fernet), `pypdf` (PDF text layer), `pytesseract` + `pdf2image` + Tesseract (`rus`/`kaz`/`eng`) for OCR (prod/Docker only), `reportlab` (test fixtures only), pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-06-15-phase2-profile-location-design.md`

> **Repo conventions:**
> - Run tests with the project venv: `.venv\Scripts\python.exe -m pytest -q` (Windows). Examples below use `pytest`; substitute the venv interpreter.
> - Profiles are keyed by `telegram_user_id` (consistent with `RoleService`), giving a 1:1 profile-per-user. This realizes the spec's "1:1 Profile↔User" without a join.
> - End every commit message with the repo's `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

---

## File Structure

```
ai-clerk/
  pyproject.toml                                  # MODIFY: add pypdf (base), reportlab (dev), [ocr] extra
  Dockerfile                                      # MODIFY: tesseract + poppler system deps, install .[ocr]
  src/ai_clerk/
    db/models.py                                  # MODIFY: add Profile model
    crypto.py                                     # (unchanged; reused)
    profile/
      __init__.py                                 # NEW (empty)
      dto.py                                      # NEW: ProfileDTO dataclass
      masking.py                                  # NEW: mask_iin, mask_document
      service.py                                  # NEW: ProfileService (encrypt/store/read)
      extraction/
        __init__.py                               # NEW (empty)
        ocr.py                                    # NEW: OcrEngine protocol, FakeOcrEngine, TesseractOcrEngine
        pdf_text.py                               # NEW: PdfTextExtractor (text-layer + OCR fallback)
        fields.py                                 # NEW: ExtractedProfile, ProfileExtractor, RegexProfileExtractor
    location/
      __init__.py                                 # NEW (empty)
      aliases.py                                  # NEW: KZ city alias table + normalize_city + city_to_iata
      airports.py                                 # NEW: Airport, AirportIndex (load CSV, nearest, by_city, by_iata)
      service.py                                  # NEW: DepartureResolution, LocationService.resolve_departure
    data/
      airports_kz.csv                             # NEW: bundled KZ airports (OurAirports column format)
    bot/
      middleware.py                               # MODIFY: inject ProfileService (needs Cipher)
      profile_handlers.py                         # NEW: /profile, document upload, confirm callbacks, location
      main.py                                     # MODIFY: build singletons, register profile router
  tests/
    fixtures/
      airports_sample.csv                         # NEW: tiny airport fixture
    test_profile_model.py                         # NEW
    test_profile_masking.py                       # NEW
    test_profile_service.py                       # NEW
    test_profile_extraction_fields.py             # NEW
    test_profile_pdf_text.py                      # NEW
    test_profile_ocr.py                           # NEW
    test_location_aliases.py                      # NEW
    test_airports.py                              # NEW
    test_location_service.py                      # NEW
```

---

## Task 1: Profile data model

**Files:**
- Modify: `src/ai_clerk/db/models.py`
- Test: `tests/test_profile_model.py`

- [ ] **Step 1: Write the failing test**

`tests/test_profile_model.py`:
```python
from sqlalchemy import select

from ai_clerk.db.models import Profile


async def test_profile_persists_with_defaults(session):
    session.add(Profile(telegram_user_id=42, prefer_faster=True))
    await session.commit()

    result = await session.execute(
        select(Profile).where(Profile.telegram_user_id == 42)
    )
    profile = result.scalar_one()
    assert profile.id is not None
    assert profile.prefer_faster is True
    assert profile.iin_enc is None          # encrypted PII defaults empty
    assert profile.budget_limit is None     # policy nullable
    assert profile.created_at is not None


async def test_profile_telegram_user_id_unique(session):
    session.add(Profile(telegram_user_id=1))
    await session.commit()
    session.add(Profile(telegram_user_id=1))
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_profile_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'Profile'`.

- [ ] **Step 3: Add the Profile model**

Append to `src/ai_clerk/db/models.py` (keep existing imports; add `Boolean, Integer, JSON, Text` to the `sqlalchemy` import line):
```python
class Profile(Base):
    """Traveler profile, 1:1 with a user (keyed by telegram_user_id).

    PII fields ending in `_enc` hold Fernet ciphertext; ProfileService is the
    only place that encrypts/decrypts them.
    """

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True
    )

    # Encrypted PII (Fernet tokens)
    full_name_enc: Mapped[str | None] = mapped_column(Text, default=None)
    iin_enc: Mapped[str | None] = mapped_column(Text, default=None)
    document_number_enc: Mapped[str | None] = mapped_column(Text, default=None)
    birth_date_enc: Mapped[str | None] = mapped_column(Text, default=None)

    # Plaintext, non-sensitive identity
    document_type: Mapped[str | None] = mapped_column(String(16), default=None)
    position: Mapped[str | None] = mapped_column(String(128), default=None)
    citizenship: Mapped[str | None] = mapped_column(String(64), default=None)

    # Preferences
    default_departure_iata: Mapped[str | None] = mapped_column(String(8), default=None)
    default_departure_city: Mapped[str | None] = mapped_column(String(128), default=None)
    preferred_airlines: Mapped[list | None] = mapped_column(JSON, default=None)
    preferred_hotels: Mapped[list | None] = mapped_column(JSON, default=None)
    seat_preference: Mapped[str | None] = mapped_column(String(32), default=None)
    meal_preference: Mapped[str | None] = mapped_column(String(64), default=None)
    prefer_faster: Mapped[bool] = mapped_column(Boolean, default=True)

    # Loyalty programs: list of {"program": str, "number": str}
    loyalty: Mapped[list | None] = mapped_column(JSON, default=None)

    # Policy / limits (nullable; stored, not yet enforced)
    budget_limit: Mapped[float | None] = mapped_column(Float, default=None)
    cabin_class: Mapped[str | None] = mapped_column(String(32), default=None)
    hotel_max_stars: Mapped[int | None] = mapped_column(Integer, default=None)
    per_diem: Mapped[float | None] = mapped_column(Float, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

The current import line in `models.py` is:
```python
from sqlalchemy import BigInteger, DateTime, Float, String
```
Change it to:
```python
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, JSON, String, Text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_profile_model.py -v`
Expected: PASS (both). `init_models` already imports `ai_clerk.db.models`, so `create_all` builds the `profiles` table automatically.

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/db/models.py tests/test_profile_model.py
git commit -m "feat: Profile model with encrypted PII fields"
```

---

## Task 2: PII masking utilities

**Files:**
- Create: `src/ai_clerk/profile/__init__.py` (empty)
- Create: `src/ai_clerk/profile/masking.py`
- Test: `tests/test_profile_masking.py`

- [ ] **Step 1: Write the failing test**

`tests/test_profile_masking.py`:
```python
from ai_clerk.profile.masking import mask_document, mask_iin


def test_mask_iin_keeps_last_four():
    assert mask_iin("900101300123") == "••••••••0123"


def test_mask_iin_handles_short_and_empty():
    assert mask_iin("12") == "••"
    assert mask_iin(None) == "—"
    assert mask_iin("") == "—"


def test_mask_document_keeps_last_three():
    assert mask_document("N12345678") == "••••••678"


def test_mask_document_handles_short_and_empty():
    assert mask_document("AB") == "••"
    assert mask_document(None) == "—"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_profile_masking.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.profile'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/profile/__init__.py`:
```python
```

`src/ai_clerk/profile/masking.py`:
```python
def mask_iin(iin: str | None) -> str:
    """Mask an IIN, revealing only the last 4 digits."""
    if not iin:
        return "—"
    value = iin.strip()
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * (len(value) - 4) + value[-4:]


def mask_document(number: str | None) -> str:
    """Mask a document number, revealing only the last 3 characters."""
    if not number:
        return "—"
    value = number.strip()
    if len(value) <= 3:
        return "•" * len(value)
    return "•" * (len(value) - 3) + value[-3:]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_profile_masking.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/profile/__init__.py src/ai_clerk/profile/masking.py tests/test_profile_masking.py
git commit -m "feat: PII masking helpers for display"
```

---

## Task 3: ProfileService (encrypt / store / read)

**Files:**
- Create: `src/ai_clerk/profile/dto.py`
- Create: `src/ai_clerk/profile/service.py`
- Test: `tests/test_profile_service.py`

- [ ] **Step 1: Write the failing test**

`tests/test_profile_service.py`:
```python
import pytest
from sqlalchemy import select

from ai_clerk.crypto import Cipher, generate_key
from ai_clerk.db.models import Profile
from ai_clerk.profile.service import ProfileService


def _service(session) -> ProfileService:
    return ProfileService(session, Cipher(generate_key()))


async def test_upsert_identity_encrypts_and_roundtrips(session):
    svc = _service(session)
    dto = await svc.upsert_identity(
        7,
        full_name="ИВАНОВ ИВАН ИВАНОВИЧ",
        iin="900101300123",
        document_type="udo",
        document_number="N12345678",
        birth_date="1990-01-01",
        position="Генеральный директор",
    )
    assert dto.full_name == "ИВАНОВ ИВАН ИВАНОВИЧ"
    assert dto.iin == "900101300123"
    assert dto.document_type == "udo"
    assert dto.position == "Генеральный директор"
    assert dto.prefer_faster is True


async def test_pii_stored_as_ciphertext(session):
    svc = _service(session)
    await svc.upsert_identity(7, iin="900101300123")

    row = (
        await session.execute(select(Profile).where(Profile.telegram_user_id == 7))
    ).scalar_one()
    assert row.iin_enc is not None
    assert "900101300123" not in row.iin_enc  # not stored in cleartext


async def test_upsert_is_partial_update(session):
    svc = _service(session)
    await svc.upsert_identity(7, full_name="A B C", iin="900101300123")
    await svc.upsert_identity(7, position="CFO")  # only position changes
    dto = await svc.get_profile(7)
    assert dto.full_name == "A B C"
    assert dto.iin == "900101300123"
    assert dto.position == "CFO"


async def test_set_default_departure(session):
    svc = _service(session)
    await svc.set_default_departure(7, iata="ALA", city="Алматы")
    dto = await svc.get_profile(7)
    assert dto.default_departure_iata == "ALA"
    assert dto.default_departure_city == "Алматы"


async def test_set_preferences_and_policy(session):
    svc = _service(session)
    await svc.set_preferences(7, preferred_airlines=["KC"], prefer_faster=False)
    await svc.set_policy(7, budget_limit=500000.0, cabin_class="economy")
    dto = await svc.get_profile(7)
    assert dto.preferred_airlines == ["KC"]
    assert dto.prefer_faster is False
    assert dto.budget_limit == 500000.0
    assert dto.cabin_class == "economy"


async def test_set_preferences_rejects_unknown_key(session):
    svc = _service(session)
    with pytest.raises(ValueError):
        await svc.set_preferences(7, nonsense=1)


async def test_get_profile_unknown_returns_none(session):
    svc = _service(session)
    assert await svc.get_profile(999) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_profile_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.profile.service'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/profile/dto.py`:
```python
from dataclasses import dataclass, field


@dataclass
class ProfileDTO:
    """Decrypted, read-only view of a profile returned by ProfileService."""

    telegram_user_id: int
    full_name: str | None = None
    iin: str | None = None
    document_type: str | None = None
    document_number: str | None = None
    birth_date: str | None = None
    position: str | None = None
    citizenship: str | None = None
    default_departure_iata: str | None = None
    default_departure_city: str | None = None
    preferred_airlines: list[str] = field(default_factory=list)
    preferred_hotels: list[str] = field(default_factory=list)
    seat_preference: str | None = None
    meal_preference: str | None = None
    prefer_faster: bool = True
    loyalty: list[dict] = field(default_factory=list)
    budget_limit: float | None = None
    cabin_class: str | None = None
    hotel_max_stars: int | None = None
    per_diem: float | None = None
```

`src/ai_clerk/profile/service.py`:
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_clerk.crypto import Cipher
from ai_clerk.db.models import Profile
from ai_clerk.profile.dto import ProfileDTO

_PREFERENCE_FIELDS = {
    "preferred_airlines",
    "preferred_hotels",
    "seat_preference",
    "meal_preference",
    "prefer_faster",
    "loyalty",
}
_POLICY_FIELDS = {"budget_limit", "cabin_class", "hotel_max_stars", "per_diem"}


class ProfileService:
    """Stores and reads traveler profiles; encrypts PII at rest via Cipher."""

    def __init__(self, session: AsyncSession, cipher: Cipher):
        self._session = session
        self._cipher = cipher

    async def upsert_identity(
        self,
        telegram_user_id: int,
        *,
        full_name: str | None = None,
        iin: str | None = None,
        document_type: str | None = None,
        document_number: str | None = None,
        birth_date: str | None = None,
        position: str | None = None,
        citizenship: str | None = None,
    ) -> ProfileDTO:
        profile = await self._get_or_create(telegram_user_id)
        if full_name is not None:
            profile.full_name_enc = self._cipher.encrypt(full_name)
        if iin is not None:
            profile.iin_enc = self._cipher.encrypt(iin)
        if document_number is not None:
            profile.document_number_enc = self._cipher.encrypt(document_number)
        if birth_date is not None:
            profile.birth_date_enc = self._cipher.encrypt(birth_date)
        if document_type is not None:
            profile.document_type = document_type
        if position is not None:
            profile.position = position
        if citizenship is not None:
            profile.citizenship = citizenship
        await self._session.commit()
        return await self.get_profile(telegram_user_id)

    async def set_default_departure(
        self, telegram_user_id: int, *, iata: str | None = None, city: str | None = None
    ) -> ProfileDTO:
        profile = await self._get_or_create(telegram_user_id)
        if iata is not None:
            profile.default_departure_iata = iata
        if city is not None:
            profile.default_departure_city = city
        await self._session.commit()
        return await self.get_profile(telegram_user_id)

    async def set_preferences(self, telegram_user_id: int, **prefs) -> ProfileDTO:
        return await self._set_fields(telegram_user_id, _PREFERENCE_FIELDS, prefs)

    async def set_policy(self, telegram_user_id: int, **limits) -> ProfileDTO:
        return await self._set_fields(telegram_user_id, _POLICY_FIELDS, limits)

    async def get_profile(self, telegram_user_id: int) -> ProfileDTO | None:
        profile = await self._get(telegram_user_id)
        if profile is None:
            return None
        return ProfileDTO(
            telegram_user_id=profile.telegram_user_id,
            full_name=self._dec(profile.full_name_enc),
            iin=self._dec(profile.iin_enc),
            document_type=profile.document_type,
            document_number=self._dec(profile.document_number_enc),
            birth_date=self._dec(profile.birth_date_enc),
            position=profile.position,
            citizenship=profile.citizenship,
            default_departure_iata=profile.default_departure_iata,
            default_departure_city=profile.default_departure_city,
            preferred_airlines=profile.preferred_airlines or [],
            preferred_hotels=profile.preferred_hotels or [],
            seat_preference=profile.seat_preference,
            meal_preference=profile.meal_preference,
            prefer_faster=profile.prefer_faster,
            loyalty=profile.loyalty or [],
            budget_limit=profile.budget_limit,
            cabin_class=profile.cabin_class,
            hotel_max_stars=profile.hotel_max_stars,
            per_diem=profile.per_diem,
        )

    async def _set_fields(
        self, telegram_user_id: int, allowed: set[str], values: dict
    ) -> ProfileDTO:
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        profile = await self._get_or_create(telegram_user_id)
        for key, value in values.items():
            setattr(profile, key, value)
        await self._session.commit()
        return await self.get_profile(telegram_user_id)

    async def _get(self, telegram_user_id: int) -> Profile | None:
        result = await self._session.execute(
            select(Profile).where(Profile.telegram_user_id == telegram_user_id)
        )
        return result.scalar_one_or_none()

    async def _get_or_create(self, telegram_user_id: int) -> Profile:
        profile = await self._get(telegram_user_id)
        if profile is None:
            # Set prefer_faster explicitly so the in-memory object matches the DB
            # default before any refresh (session uses expire_on_commit=False).
            profile = Profile(telegram_user_id=telegram_user_id, prefer_faster=True)
            self._session.add(profile)
        return profile

    def _dec(self, token: str | None) -> str | None:
        return self._cipher.decrypt(token) if token is not None else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_profile_service.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/profile/dto.py src/ai_clerk/profile/service.py tests/test_profile_service.py
git commit -m "feat: ProfileService with encrypted PII storage and DTO reads"
```

---

## Task 4: Field extraction (ExtractedProfile + RegexProfileExtractor)

**Files:**
- Create: `src/ai_clerk/profile/extraction/__init__.py` (empty)
- Create: `src/ai_clerk/profile/extraction/fields.py`
- Test: `tests/test_profile_extraction_fields.py`

- [ ] **Step 1: Write the failing test**

`tests/test_profile_extraction_fields.py`:
```python
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
    )


def test_missing_fields_are_none():
    result = RegexProfileExtractor().extract("просто текст без данных")
    assert result == ExtractedProfile()


def test_extracts_partial():
    result = RegexProfileExtractor().extract("ИИН 123456789012 и больше ничего")
    assert result.iin == "123456789012"
    assert result.full_name is None
    assert result.document_number is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_profile_extraction_fields.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.profile.extraction'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/profile/extraction/__init__.py`:
```python
```

`src/ai_clerk/profile/extraction/fields.py`:
```python
import re
from dataclasses import dataclass
from typing import Protocol

_IIN_RE = re.compile(r"\b(\d{12})\b")
_DATE_RE = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")
_DOC_RE = re.compile(r"\b(N\s?\d{6,9})\b", re.IGNORECASE)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_profile_extraction_fields.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/profile/extraction/__init__.py src/ai_clerk/profile/extraction/fields.py tests/test_profile_extraction_fields.py
git commit -m "feat: regex profile field extractor"
```

---

## Task 5: OCR engine interface (Fake + Tesseract adapter)

**Files:**
- Create: `src/ai_clerk/profile/extraction/ocr.py`
- Test: `tests/test_profile_ocr.py`

- [ ] **Step 1: Write the failing test**

`tests/test_profile_ocr.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_profile_ocr.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.profile.extraction.ocr'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/profile/extraction/ocr.py`:
```python
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
    exercised in Docker (see Task 11 manual verification).
    """

    def __init__(self, dpi: int = 300):
        self._dpi = dpi

    def recognize_pdf(self, pdf_bytes: bytes, langs: str = "rus+kaz+eng") -> str:
        from pdf2image import convert_from_bytes
        import pytesseract

        images = convert_from_bytes(pdf_bytes, dpi=self._dpi)
        return "\n".join(
            pytesseract.image_to_string(image, lang=langs) for image in images
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_profile_ocr.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/profile/extraction/ocr.py tests/test_profile_ocr.py
git commit -m "feat: OCR engine interface with Fake and Tesseract adapters"
```

---

## Task 6: PdfTextExtractor (text-layer first, OCR fallback) + deps

**Files:**
- Modify: `pyproject.toml` (add `pypdf` base dep, `reportlab` dev dep)
- Create: `src/ai_clerk/profile/extraction/pdf_text.py`
- Test: `tests/test_profile_pdf_text.py`

- [ ] **Step 1: Add dependencies**

In `pyproject.toml`, add `"pypdf>=5.1"` to `[project].dependencies`, and `"reportlab>=4.2"` to `[project.optional-dependencies].dev`. Resulting blocks:
```toml
dependencies = [
    "aiogram>=3.13",
    "pydantic-settings>=2.5",
    "cryptography>=43",
    "sqlalchemy>=2.0.36",
    "asyncpg>=0.30",
    "itsdangerous>=2.2",
    "pypdf>=5.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "aiosqlite>=0.20",
    "ruff>=0.7",
    "reportlab>=4.2",
]
```

Run: `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
Expected: installs `pypdf` and `reportlab` for Python 3.14.x.

- [ ] **Step 2: Write the failing test**

`tests/test_profile_pdf_text.py`:
```python
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
    out = extractor.extract_text(_pdf_with_text("ИИН 900101300123"))
    assert "900101300123" in out
    assert ocr.calls == 0  # text layer made OCR unnecessary


def test_falls_back_to_ocr_when_no_text_layer():
    ocr = FakeOcrEngine(text="OCR-FALLBACK TEXT")
    extractor = PdfTextExtractor(ocr)
    out = extractor.extract_text(_blank_pdf())
    assert out == "OCR-FALLBACK TEXT"
    assert ocr.calls == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_profile_pdf_text.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.profile.extraction.pdf_text'`.

- [ ] **Step 4: Write the implementation**

`src/ai_clerk/profile/extraction/pdf_text.py`:
```python
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
        text = self._text_layer(pdf_bytes)
        if len(text.strip()) >= self._min_text_len:
            return text
        return self._ocr.recognize_pdf(pdf_bytes)

    @staticmethod
    def _text_layer(pdf_bytes: bytes) -> str:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_profile_pdf_text.py -v`
Expected: PASS (both).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ai_clerk/profile/extraction/pdf_text.py tests/test_profile_pdf_text.py
git commit -m "feat: PDF text extractor with OCR fallback"
```

---

## Task 7: KZ city aliases

**Files:**
- Create: `src/ai_clerk/location/__init__.py` (empty)
- Create: `src/ai_clerk/location/aliases.py`
- Test: `tests/test_location_aliases.py`

- [ ] **Step 1: Write the failing test**

`tests/test_location_aliases.py`:
```python
from ai_clerk.location.aliases import city_to_iata, normalize_city


def test_normalize_lowercases_trims_and_collapses():
    assert normalize_city("  Алма-Ата  ") == "алма-ата"
    assert normalize_city("Нур-Султан") == "нур-султан"


def test_aliases_map_to_iata():
    assert city_to_iata("Алматы") == "ALA"
    assert city_to_iata("almaty") == "ALA"
    assert city_to_iata("Алма-Ата") == "ALA"
    assert city_to_iata("Астана") == "NQZ"
    assert city_to_iata("Нур-Султан") == "NQZ"
    assert city_to_iata("Шымкент") == "CIT"


def test_unknown_city_returns_none():
    assert city_to_iata("Париж") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_location_aliases.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.location'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/location/__init__.py`:
```python
```

`src/ai_clerk/location/aliases.py`:
```python
def normalize_city(name: str) -> str:
    """Lowercase, replace ё→е, trim, and collapse internal whitespace."""
    return " ".join(name.strip().lower().replace("ё", "е").split())


# Common RU/KK/EN spellings of Kazakhstan cities → airport IATA code.
CITY_ALIASES: dict[str, str] = {
    # Almaty
    "алматы": "ALA", "almaty": "ALA", "алма-ата": "ALA", "alma-ata": "ALA",
    # Astana
    "астана": "NQZ", "astana": "NQZ", "нур-султан": "NQZ", "nur-sultan": "NQZ",
    "нурсултан": "NQZ", "nursultan": "NQZ", "целиноград": "NQZ",
    # Shymkent
    "шымкент": "CIT", "shymkent": "CIT", "чимкент": "CIT", "chimkent": "CIT",
    # Aktobe
    "актобе": "AKX", "aktobe": "AKX", "актюбинск": "AKX",
    # Atyrau
    "атырау": "GUW", "atyrau": "GUW", "гурьев": "GUW",
    # Karaganda
    "караганда": "KGF", "karaganda": "KGF", "qaraganda": "KGF",
    # Aktau
    "актау": "SCO", "aktau": "SCO", "шевченко": "SCO",
    # Taraz
    "тараз": "DMZ", "taraz": "DMZ", "джамбул": "DMZ", "жамбыл": "DMZ",
    # Pavlodar
    "павлодар": "PWQ", "pavlodar": "PWQ",
    # Oral / Uralsk
    "уральск": "URA", "oral": "URA", "орал": "URA",
    # Oskemen / Ust-Kamenogorsk
    "усть-каменогорск": "UKK", "oskemen": "UKK", "ust-kamenogorsk": "UKK",
    "оскемен": "UKK",
    # Kostanay
    "костанай": "KSN", "kostanay": "KSN", "кустанай": "KSN",
    # Kyzylorda
    "кызылорда": "KZO", "kyzylorda": "KZO", "qyzylorda": "KZO",
    # Petropavl
    "петропавловск": "PPK", "petropavl": "PPK", "петропавл": "PPK",
    # Semey
    "семей": "PLX", "semey": "PLX", "семипалатинск": "PLX",
    # Turkistan
    "туркестан": "HSA", "turkistan": "HSA", "turkestan": "HSA",
    # Kokshetau
    "кокшетау": "KOV", "kokshetau": "KOV",
}


def city_to_iata(name: str) -> str | None:
    return CITY_ALIASES.get(normalize_city(name))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_location_aliases.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/location/__init__.py src/ai_clerk/location/aliases.py tests/test_location_aliases.py
git commit -m "feat: KZ city alias table"
```

---

## Task 8: Airport dataset + AirportIndex

**Files:**
- Create: `src/ai_clerk/data/airports_kz.csv`
- Create: `tests/fixtures/airports_sample.csv`
- Create: `src/ai_clerk/location/airports.py`
- Test: `tests/test_airports.py`

- [ ] **Step 1: Create the bundled KZ airports CSV**

`src/ai_clerk/data/airports_kz.csv` (OurAirports column names; KZ subset — refresh later from the full OurAirports `airports.csv` by filtering `iso_country == KZ` and non-empty `iata_code`):
```csv
iata_code,name,municipality,latitude_deg,longitude_deg,iso_country
ALA,Almaty International Airport,Almaty,43.352100,77.040497,KZ
NQZ,Nursultan Nazarbayev International Airport,Astana,51.022202,71.466904,KZ
CIT,Shymkent International Airport,Shymkent,42.364201,69.478897,KZ
AKX,Aktobe International Airport,Aktobe,50.245800,57.206699,KZ
GUW,Atyrau International Airport,Atyrau,47.121898,51.821400,KZ
KGF,Sary-Arka Airport,Karaganda,49.670799,73.334396,KZ
SCO,Aktau Airport,Aktau,43.860100,51.091900,KZ
DMZ,Taraz Airport,Taraz,42.853600,71.303596,KZ
PWQ,Pavlodar Airport,Pavlodar,52.195000,77.073898,KZ
URA,Oral Ak Zhol Airport,Oral,51.150799,51.543098,KZ
UKK,Oskemen Airport,Oskemen,50.036598,82.494202,KZ
KSN,Kostanay West Airport,Kostanay,53.206902,63.550301,KZ
KZO,Kyzylorda Airport,Kyzylorda,44.706902,65.592499,KZ
PPK,Petropavl Airport,Petropavl,54.774700,69.183899,KZ
PLX,Semey Airport,Semey,50.351299,80.234398,KZ
HSA,Hazret Sultan International Airport,Turkistan,43.313301,68.146896,KZ
KOV,Kokshetau Airport,Kokshetau,53.329102,69.594597,KZ
```

`tests/fixtures/airports_sample.csv` (small, deterministic fixture for index unit tests):
```csv
iata_code,name,municipality,latitude_deg,longitude_deg,iso_country
ALA,Almaty International Airport,Almaty,43.352100,77.040497,KZ
NQZ,Nursultan Nazarbayev International Airport,Astana,51.022202,71.466904,KZ
CIT,Shymkent International Airport,Shymkent,42.364201,69.478897,KZ
```

- [ ] **Step 2: Write the failing test**

`tests/test_airports.py`:
```python
from pathlib import Path

from ai_clerk.location.airports import AirportIndex

FIXTURE = Path(__file__).parent / "fixtures" / "airports_sample.csv"


def _index() -> AirportIndex:
    return AirportIndex.from_csv(FIXTURE)


def test_by_iata():
    airport = _index().by_iata("ala")
    assert airport is not None
    assert airport.iata == "ALA"
    assert airport.city == "Almaty"


def test_by_city_via_alias():
    # "Алматы" is an alias mapping to ALA even though the CSV city is "Almaty".
    assert _index().by_city("Алматы").iata == "ALA"


def test_by_city_via_municipality():
    assert _index().by_city("Astana").iata == "NQZ"


def test_nearest_returns_closest_airport():
    index = _index()
    # Coordinates in central Almaty → ALA, not NQZ/CIT.
    assert index.nearest(43.238949, 76.889709).iata == "ALA"
    # Coordinates near Astana → NQZ.
    assert index.nearest(51.160520, 71.470355).iata == "NQZ"


def test_bundled_dataset_loads():
    index = AirportIndex.bundled()
    assert index.by_iata("NQZ") is not None
    assert index.by_iata("ALA") is not None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_airports.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.location.airports'`.

- [ ] **Step 4: Write the implementation**

`src/ai_clerk/location/airports.py`:
```python
import csv
import math
from dataclasses import dataclass
from pathlib import Path

from ai_clerk.location.aliases import city_to_iata, normalize_city

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "airports_kz.csv"
_EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Airport:
    iata: str
    name: str
    city: str
    lat: float
    lon: float
    country: str


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class AirportIndex:
    """In-memory airport lookup: by IATA, by city (alias-aware), and nearest."""

    def __init__(self, airports: list[Airport]):
        self._airports = airports
        self._by_iata = {a.iata.upper(): a for a in airports if a.iata}
        self._by_city: dict[str, Airport] = {}
        for airport in airports:
            if airport.city:
                self._by_city.setdefault(normalize_city(airport.city), airport)

    @classmethod
    def from_csv(cls, path) -> "AirportIndex":
        airports: list[Airport] = []
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                iata = (row.get("iata_code") or "").strip()
                lat = row.get("latitude_deg")
                lon = row.get("longitude_deg")
                if not iata or not lat or not lon:
                    continue
                airports.append(
                    Airport(
                        iata=iata,
                        name=(row.get("name") or "").strip(),
                        city=(row.get("municipality") or "").strip(),
                        lat=float(lat),
                        lon=float(lon),
                        country=(row.get("iso_country") or "").strip(),
                    )
                )
        return cls(airports)

    @classmethod
    def bundled(cls) -> "AirportIndex":
        return cls.from_csv(_DATA_PATH)

    def by_iata(self, code: str) -> Airport | None:
        return self._by_iata.get(code.strip().upper())

    def by_city(self, name: str) -> Airport | None:
        iata = city_to_iata(name)
        if iata and iata in self._by_iata:
            return self._by_iata[iata]
        return self._by_city.get(normalize_city(name))

    def nearest(self, lat: float, lon: float) -> Airport | None:
        if not self._airports:
            return None
        return min(
            self._airports,
            key=lambda a: _haversine_km(lat, lon, a.lat, a.lon),
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_airports.py -v`
Expected: PASS (all). Note: the wheel build (`[tool.hatch.build.targets.wheel]`) packages `src/ai_clerk`, so `data/airports_kz.csv` ships with the package.

- [ ] **Step 6: Commit**

```bash
git add src/ai_clerk/data/airports_kz.csv tests/fixtures/airports_sample.csv src/ai_clerk/location/airports.py tests/test_airports.py
git commit -m "feat: bundled KZ airports dataset and AirportIndex"
```

---

## Task 9: LocationService (departure resolver)

**Files:**
- Create: `src/ai_clerk/location/service.py`
- Test: `tests/test_location_service.py`

- [ ] **Step 1: Write the failing test**

`tests/test_location_service.py`:
```python
from pathlib import Path

from ai_clerk.location.airports import AirportIndex
from ai_clerk.location.service import DepartureResolution, LocationService

FIXTURE = Path(__file__).parent / "fixtures" / "airports_sample.csv"


def _service() -> LocationService:
    return LocationService(AirportIndex.from_csv(FIXTURE))


def test_explicit_city_wins():
    res = _service().resolve_departure(
        explicit_city="Астана",
        coords=(43.238949, 76.889709),  # would be ALA if used
        profile_default="Шымкент",
    )
    assert res == DepartureResolution(airport=_service()._index.by_iata("NQZ"), source="explicit")


def test_coords_used_when_no_explicit_city():
    res = _service().resolve_departure(coords=(43.238949, 76.889709))
    assert res.airport.iata == "ALA"
    assert res.source == "coordinates"


def test_profile_default_used_last():
    res = _service().resolve_departure(profile_default="ALA")
    assert res.airport.iata == "ALA"
    assert res.source == "profile_default"


def test_unresolvable_returns_none():
    res = _service().resolve_departure(explicit_city="Париж")
    assert res is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_location_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.location.service'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/location/service.py`:
```python
from dataclasses import dataclass

from ai_clerk.location.airports import Airport, AirportIndex


@dataclass
class DepartureResolution:
    airport: Airport
    source: str  # "explicit" | "coordinates" | "profile_default"


class LocationService:
    """Resolves the trip's departure airport per spec §5 priority chain."""

    def __init__(self, index: AirportIndex):
        self._index = index

    def resolve_departure(
        self,
        *,
        explicit_city: str | None = None,
        coords: tuple[float, float] | None = None,
        profile_default: str | None = None,
    ) -> DepartureResolution | None:
        if explicit_city:
            airport = self._index.by_city(explicit_city)
            if airport:
                return DepartureResolution(airport, "explicit")
        if coords:
            airport = self._index.nearest(coords[0], coords[1])
            if airport:
                return DepartureResolution(airport, "coordinates")
        if profile_default:
            airport = self._index.by_city(profile_default) or self._index.by_iata(
                profile_default
            )
            if airport:
                return DepartureResolution(airport, "profile_default")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_location_service.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/location/service.py tests/test_location_service.py
git commit -m "feat: LocationService departure-point resolver"
```

---

## Task 10: OCR system dependencies (Docker)

**Files:**
- Modify: `pyproject.toml` (add `[project.optional-dependencies].ocr`)
- Modify: `Dockerfile`

> Ops task. The `ocr` extra and Tesseract/poppler binaries are only needed in production; dev/test stays light (uses `FakeOcrEngine`). Verify by building the image.

- [ ] **Step 1: Add the `ocr` optional dependency group**

In `pyproject.toml`, add under `[project.optional-dependencies]`:
```toml
ocr = [
    "pytesseract>=0.3.13",
    "pdf2image>=1.17",
    "pillow>=10.4",
]
```

- [ ] **Step 2: Update the Dockerfile**

Replace `Dockerfile` with:
```dockerfile
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# OCR runtime: Tesseract (rus/kaz/eng language data) + poppler for pdf2image
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-kaz \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip && pip install ".[ocr]"

CMD ["python", "-m", "ai_clerk.bot.main"]
```

- [ ] **Step 3: Validate the build**

Run: `docker build -t ai-clerk:phase2 .`
Expected: image builds; `pip install ".[ocr]"` resolves `pytesseract`/`pdf2image`/`pillow`; apt installs Tesseract + language data + poppler with no errors.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml Dockerfile
git commit -m "chore: add OCR runtime deps (tesseract rus/kaz/eng + poppler)"
```

---

## Task 11: Bot wiring — profile & location handlers (manual run verification)

**Files:**
- Modify: `src/ai_clerk/bot/middleware.py`
- Create: `src/ai_clerk/bot/profile_handlers.py`
- Modify: `src/ai_clerk/bot/main.py`

> Glue between aiogram and the tested services above. No unit test; verify by running the bot. All branching logic it relies on (ProfileService, extraction, LocationService) is already covered by Tasks 3–9. Pending extractions are held in a per-user in-memory dict (single-process MVP); the decrypted values live in memory only until the director saves or discards.

- [ ] **Step 1: Inject ProfileService via the middleware**

Replace `src/ai_clerk/bot/middleware.py` with:
```python
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from ai_clerk.crypto import Cipher
from ai_clerk.profile.service import ProfileService
from ai_clerk.roles.service import RoleService


class DependencyMiddleware(BaseMiddleware):
    """Opens a DB session per update and injects services into handlers."""

    def __init__(self, session_factory: async_sessionmaker, cipher: Cipher):
        self._session_factory = session_factory
        self._cipher = cipher

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["session"] = session
            data["role_service"] = RoleService(session)
            data["profile_service"] = ProfileService(session, self._cipher)
            return await handler(event, data)
```

- [ ] **Step 2: Write the profile/location handlers**

`src/ai_clerk/bot/profile_handlers.py`:
```python
import io

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from ai_clerk.bot.permissions import is_allowed
from ai_clerk.location.service import LocationService
from ai_clerk.profile.dto import ProfileDTO
from ai_clerk.profile.extraction.fields import (
    ExtractedProfile,
    ProfileExtractor,
)
from ai_clerk.profile.extraction.pdf_text import PdfTextExtractor
from ai_clerk.profile.masking import mask_document, mask_iin
from ai_clerk.profile.service import ProfileService
from ai_clerk.roles.service import RoleService


def _profile_summary(dto: ProfileDTO | None) -> str:
    if dto is None:
        return (
            "Профиль пуст. Пришлите PDF-документ с вашими данными "
            "(паспорт/удостоверение) — я распознаю их локально."
        )
    departure = dto.default_departure_iata or dto.default_departure_city or "—"
    return (
        "Ваш профиль:\n"
        f"• ФИО: {dto.full_name or '—'}\n"
        f"• ИИН: {mask_iin(dto.iin)}\n"
        f"• Документ: {dto.document_type or '—'} {mask_document(dto.document_number)}\n"
        f"• Должность: {dto.position or '—'}\n"
        f"• Город вылета по умолчанию: {departure}\n\n"
        "Чтобы обновить личные данные — пришлите PDF-документ. "
        "Чтобы задать город вылета — /location."
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сохранить", callback_data="profile:save"),
                InlineKeyboardButton(text="Загрузить заново", callback_data="profile:redo"),
            ]
        ]
    )


def _masked_confirmation(extracted: ExtractedProfile) -> str:
    return (
        "Распознал данные (показаны маскированно):\n"
        f"• ФИО: {extracted.full_name or '—'}\n"
        f"• ИИН: {mask_iin(extracted.iin)}\n"
        f"• № документа: {mask_document(extracted.document_number)}\n"
        f"• Дата рождения: {extracted.birth_date or '—'}\n\n"
        "Сохранить в зашифрованном виде?"
    )


def build_profile_router(
    location_service: LocationService,
    pdf_extractor: PdfTextExtractor,
    field_extractor: ProfileExtractor,
) -> Router:
    router = Router()
    # Per-user pending extraction, awaiting confirmation (in-memory, single-process).
    pending: dict[int, ExtractedProfile] = {}

    async def _ensure_can_edit(message: Message, role_service: RoleService) -> bool:
        role = await role_service.get_role(message.from_user.id)
        if not is_allowed(role, "profile.edit"):
            await message.answer("Недостаточно прав для редактирования профиля.")
            return False
        return True

    @router.message(Command("profile"))
    async def on_profile(
        message: Message,
        role_service: RoleService,
        profile_service: ProfileService,
    ) -> None:
        if not await _ensure_can_edit(message, role_service):
            return
        dto = await profile_service.get_profile(message.from_user.id)
        await message.answer(_profile_summary(dto))

    @router.message(F.document)
    async def on_document(
        message: Message,
        role_service: RoleService,
    ) -> None:
        if not await _ensure_can_edit(message, role_service):
            return
        file = await message.bot.get_file(message.document.file_id)
        buffer = io.BytesIO()
        await message.bot.download(file, destination=buffer)
        text = pdf_extractor.extract_text(buffer.getvalue())
        extracted = field_extractor.extract(text)
        pending[message.from_user.id] = extracted
        await message.answer(_masked_confirmation(extracted), reply_markup=_confirm_keyboard())

    @router.callback_query(F.data == "profile:save")
    async def on_save(
        callback: CallbackQuery,
        profile_service: ProfileService,
    ) -> None:
        extracted = pending.pop(callback.from_user.id, None)
        if extracted is None:
            await callback.answer("Нет данных для сохранения.", show_alert=True)
            return
        await profile_service.upsert_identity(
            callback.from_user.id,
            full_name=extracted.full_name,
            iin=extracted.iin,
            document_number=extracted.document_number,
            birth_date=extracted.birth_date,
        )
        await callback.message.edit_text("Данные сохранены в зашифрованном виде.")
        await callback.answer()

    @router.callback_query(F.data == "profile:redo")
    async def on_redo(callback: CallbackQuery) -> None:
        pending.pop(callback.from_user.id, None)
        await callback.message.edit_text(
            "Хорошо, пришлите PDF-документ заново."
        )
        await callback.answer()

    @router.message(Command("location"))
    async def on_location_prompt(
        message: Message,
        role_service: RoleService,
    ) -> None:
        if not await _ensure_can_edit(message, role_service):
            return
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📍 Поделиться геопозицией", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.answer(
            "Поделитесь геопозицией — найду ближайший аэропорт.",
            reply_markup=keyboard,
        )

    @router.message(F.location)
    async def on_location(
        message: Message,
        role_service: RoleService,
        profile_service: ProfileService,
    ) -> None:
        if not await _ensure_can_edit(message, role_service):
            return
        resolution = location_service.resolve_departure(
            coords=(message.location.latitude, message.location.longitude)
        )
        if resolution is None:
            await message.answer("Не удалось определить ближайший аэропорт.")
            return
        airport = resolution.airport
        await profile_service.set_default_departure(
            message.from_user.id, iata=airport.iata, city=airport.city
        )
        await message.answer(
            f"Ближайший аэропорт: {airport.name} ({airport.iata}). "
            "Запомнил как город вылета по умолчанию."
        )

    return router
```

- [ ] **Step 3: Wire singletons and the router in `main.py`**

In `src/ai_clerk/bot/main.py`, add imports near the existing ones:
```python
from ai_clerk.bot.profile_handlers import build_profile_router
from ai_clerk.crypto import Cipher
from ai_clerk.location.airports import AirportIndex
from ai_clerk.location.service import LocationService
from ai_clerk.profile.extraction.fields import RegexProfileExtractor
from ai_clerk.profile.extraction.ocr import TesseractOcrEngine
from ai_clerk.profile.extraction.pdf_text import PdfTextExtractor
```

Then inside `main()`, after `session_factory = create_session_factory(engine)` and before creating the `Dispatcher`, construct the singletons:
```python
    cipher = Cipher(settings.fernet_key)
    location_service = LocationService(AirportIndex.bundled())
    pdf_extractor = PdfTextExtractor(TesseractOcrEngine())
    field_extractor = RegexProfileExtractor()
```

Update the middleware registration to pass the cipher:
```python
    dp.update.middleware(DependencyMiddleware(session_factory, cipher))
```

After the existing `@dp.message(...)` handlers are registered (or right after creating `dp`), include the profile router:
```python
    dp.include_router(
        build_profile_router(location_service, pdf_extractor, field_extractor)
    )
```
> Note: keep the existing inline `@dp.message(CommandStart())` and `@dp.message(Command("invite"))` handlers on `dp` as they are. Router inclusion order does not conflict because the profile router only matches `/profile`, `/location`, documents, locations, and `profile:*` callbacks.

- [ ] **Step 4: Run the full test suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all Phase 1 tests plus the new Phase 2 tests PASS. (The bot module imports cleanly because `TesseractOcrEngine` lazy-imports poppler/pytesseract.)

- [ ] **Step 5: Manual verification (local, no OCR needed for text PDFs)**

Ensure `.env` is configured (from Phase 1). Run: `.venv\Scripts\python.exe -m ai_clerk.bot.main`
In Telegram, as the onboarded DIRECTOR/ADMIN:
1. `/profile` → bot shows the empty-profile prompt.
2. Send a **text-based** PDF containing `ФИО:`, `ИИН`, `№ документа`, `Дата рождения` lines → bot replies with **masked** values + Сохранить/Загрузить заново.
3. Tap **Сохранить** → "Данные сохранены…"; `/profile` now shows masked PII.
4. `/location` → tap **Поделиться геопозицией** → bot replies with the nearest airport and stores it as the default departure.

- [ ] **Step 6: Commit**

```bash
git add src/ai_clerk/bot/middleware.py src/ai_clerk/bot/profile_handlers.py src/ai_clerk/bot/main.py
git commit -m "feat: profile (PDF upload) and location handlers wired into bot"
```

---

## Task 12: Manual OCR verification in Docker (scanned PDF)

> Optional but recommended: confirms the real Tesseract path works for scanned/image PDFs. Not a unit test (covered conceptually by Task 6 fallback wiring); this exercises the production adapter end-to-end.

- [ ] **Step 1: Build and start the stack**

Run: `docker compose up --build`
Expected: `db` becomes healthy; `bot` starts polling. (Requires a valid `.env` with `BOT_TOKEN`.)

- [ ] **Step 2: Verify OCR path**

In Telegram, send a **scanned/photo PDF** (no text layer) of an identity document. Expected: the bot still returns masked extracted fields (text-layer extraction returns near-empty → OCR fallback runs Tesseract with `rus+kaz+eng`).

- [ ] **Step 3: (If issues) Inspect logs**

Run: `docker compose logs bot`
Expected: no `pdf2image`/`pytesseract` import errors and no missing-language errors. If a language is missing, confirm `tesseract-ocr-kaz`/`-rus`/`-eng` are installed in the image (Task 10).

> No commit required unless fixes are made.

---

## Self-Review

**Spec coverage** (against `2026-06-15-phase2-profile-location-design.md`):
- §3 Profile model (encrypted PII, plaintext prefs/policy, prefer_faster) → Task 1. ✓
- §3 ProfileService (upsert_identity/set_preferences/set_policy/set_default_departure/get_profile, decrypted DTO) → Task 3. ✓
- §4 PDF→text(text-layer/OCR)→extract→masked confirm→encrypt+store: PdfTextExtractor → Task 6; OcrEngine (Fake/Tesseract) → Task 5; RegexProfileExtractor → Task 4; masked confirmation + save → Task 11; masking → Task 2. ✓
- §5 AirportIndex (nearest/by_city/by_iata), KZ aliases, resolve_departure chain, request_location UX, opt-in remember → Tasks 7, 8, 9, 11. ✓
- §6 Access control `profile.edit` (DIRECTOR/ADMIN) → Task 11 (`_ensure_can_edit`). ✓
- §7 Testing (offline, FakeOcrEngine, skip real OCR to Docker) → Tasks 1–9 unit tests; Tasks 11–12 manual. ✓
- §8 Deps + Docker (pypdf base, reportlab dev, ocr extra, Tesseract rus/kaz/eng + poppler) → Tasks 6, 10. ✓
- Deferred items (Nominatim, LLM extractor, non-KZ OCR, NLU city parsing, policy enforcement) → correctly out of scope. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases". Empty `__init__.py` files shown as intentionally empty code blocks. ✓

**Type consistency:** `ProfileService` method names/signatures match across Tasks 3 and 11; `ExtractedProfile` fields (`full_name`, `iin`, `document_number`, `birth_date`) match across Tasks 4, 6, 11; `OcrEngine.recognize_pdf(pdf_bytes, langs)` matches across Tasks 5, 6; `AirportIndex` (`from_csv`, `bundled`, `by_iata`, `by_city`, `nearest`) and `Airport` (`iata`, `name`, `city`, `lat`, `lon`, `country`) match across Tasks 8, 9, 11; `LocationService.resolve_departure(explicit_city, coords, profile_default)` + `DepartureResolution(airport, source)` match across Tasks 9, 11; `DependencyMiddleware(session_factory, cipher)` updated consistently in Tasks 11 (middleware + main). ✓
