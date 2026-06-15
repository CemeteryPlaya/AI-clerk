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
