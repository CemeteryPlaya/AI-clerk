import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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
    assert profile.updated_at is not None


async def test_profile_telegram_user_id_unique(session):
    session.add(Profile(telegram_user_id=1))
    await session.commit()
    session.add(Profile(telegram_user_id=1))
    with pytest.raises(IntegrityError):
        await session.commit()
