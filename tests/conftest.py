import pytest_asyncio
from sqlalchemy.pool import StaticPool

from ai_clerk.db.base import create_engine, create_session_factory, init_models


@pytest_asyncio.fixture
async def session():
    engine = create_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    await init_models(engine)
    factory = create_session_factory(engine)
    async with factory() as db_session:
        yield db_session
    await engine.dispose()
