from sqlalchemy import select

from ai_clerk.db.models import User


async def test_can_persist_and_query_user(session):
    session.add(User(telegram_user_id=42, chat_id=42, role="director"))
    await session.commit()

    result = await session.execute(
        select(User).where(User.telegram_user_id == 42)
    )
    user = result.scalar_one()
    assert user.id is not None
    assert user.role == "director"
    assert user.created_at is not None
