# Phase 1 — Foundation & Core Bot Skeleton — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a runnable Telegram bot with configuration, encryption utilities, a database layer, hardcoded roles (ADMIN/DIRECTOR/ACCOUNTANT), invite-link onboarding, and role-based access control.

**Architecture:** Modular monolith (Python 3.14 + aiogram 3.x). Pure logic lives in small, testable modules (`config`, `crypto`, `roles`, `bot`); the aiogram layer is thin glue. Persistence via SQLAlchemy 2.0 async (SQLite for tests, PostgreSQL in production). Onboarding uses signed, time-limited invite tokens (itsdangerous) embedded in Telegram deep links.

**Tech Stack:** Python 3.14.x, aiogram 3.x, pydantic-settings, cryptography (Fernet), SQLAlchemy 2.0 async + asyncpg/aiosqlite, itsdangerous, pytest + pytest-asyncio, Docker.

> **Roadmap (subsequent plans, not in this file):** Plan 2 — Profile & Location; Plan 3 — Trip orchestration & search (mock provider); Plan 4 — Browser-agent booking & OTP; Plan 5 — Order generation & archive/index. This plan is self-contained: it produces a bot you can talk to and onboard users into roles.

> **Note on versions:** Version pins below are indicative for mid-2026. At install time, verify Python 3.14.x compatibility of each dependency (per spec §9) and pin exact working versions.

---

## File Structure

```
ai-clerk/
  pyproject.toml                      # project metadata + deps (NEW)
  .env.example                        # documented env vars (NEW)
  Dockerfile                          # app image (NEW)
  docker-compose.yml                  # app + postgres (NEW)
  src/ai_clerk/
    __init__.py                       # version (NEW)
    config.py                         # Settings (pydantic-settings) (NEW)
    crypto.py                         # Cipher (Fernet) (NEW)
    db/
      __init__.py                     # (NEW)
      base.py                         # engine/session/Base/init_models (NEW)
      models.py                       # User ORM model (NEW)
    roles/
      __init__.py                     # (NEW)
      enums.py                        # Role enum (NEW)
      invites.py                      # InviteService (signed tokens) (NEW)
      service.py                      # RoleService (DB-backed) (NEW)
    bot/
      __init__.py                     # (NEW)
      permissions.py                  # ROLE_PERMISSIONS, is_allowed (NEW)
      onboarding.py                   # handle_start logic (NEW)
      admin.py                        # invite-link builders (NEW)
      middleware.py                   # DB session + services injection (NEW)
      main.py                         # aiogram wiring + entrypoint (NEW)
  tests/
    conftest.py                       # async db session fixture (NEW)
    test_smoke.py                     # (NEW)
    test_config.py                    # (NEW)
    test_crypto.py                    # (NEW)
    test_invites.py                   # (NEW)
    test_role_service.py              # (NEW)
    test_permissions.py               # (NEW)
    test_onboarding.py                # (NEW)
    test_admin.py                     # (NEW)
```

---

## Task 1: Project scaffold + smoke test

**Files:**
- Create: `pyproject.toml`
- Create: `src/ai_clerk/__init__.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:
```python
from ai_clerk import __version__


def test_version():
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk'`

- [ ] **Step 3: Create the project files**

`pyproject.toml`:
```toml
[project]
name = "ai-clerk"
version = "0.1.0"
description = "Personal AI secretary Telegram bot (business trips module)"
requires-python = ">=3.14"
dependencies = [
    "aiogram>=3.13",
    "pydantic-settings>=2.5",
    "cryptography>=43",
    "sqlalchemy>=2.0.36",
    "asyncpg>=0.30",
    "itsdangerous>=2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "aiosqlite>=0.20",
    "ruff>=0.7",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ai_clerk"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```

`src/ai_clerk/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Install dev dependencies**

Run: `pip install -e ".[dev]"`
Expected: installs successfully (resolves all deps for Python 3.14.x).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ai_clerk/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold ai_clerk package with smoke test"
```

---

## Task 2: Configuration (Settings)

**Files:**
- Create: `src/ai_clerk/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from ai_clerk.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    monkeypatch.setenv("SECRET_KEY", "s3cret")
    monkeypatch.setenv("FERNET_KEY", "key-placeholder")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "[111, 222]")

    s = Settings(_env_file=None)

    assert s.bot_token == "123:abc"
    assert s.secret_key == "s3cret"
    assert s.admin_telegram_ids == [111, 222]
    assert s.database_url.startswith("sqlite")  # default
    assert s.invite_ttl_seconds == 86400        # default


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "x")
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("FERNET_KEY", "x")

    s = Settings(_env_file=None)

    assert s.admin_telegram_ids == []
    assert s.log_level == "INFO"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.config'`

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str

    # Security
    secret_key: str          # signs invite tokens
    fernet_key: str          # encrypts PII at rest

    # Persistence
    database_url: str = "sqlite+aiosqlite:///./ai_clerk.db"

    # Access / onboarding
    admin_telegram_ids: list[int] = []
    invite_ttl_seconds: int = 86400  # 24h

    # Ops
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Create `.env.example`**

`.env.example`:
```dotenv
# Telegram bot token from @BotFather
BOT_TOKEN=123456:replace-me
# Random secret for signing invite tokens (e.g. `python -c "import secrets;print(secrets.token_urlsafe(32))"`)
SECRET_KEY=replace-me
# Fernet key for PII encryption (generate with: python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
FERNET_KEY=replace-me
# Production example: postgresql+asyncpg://user:pass@db:5432/ai_clerk
DATABASE_URL=sqlite+aiosqlite:///./ai_clerk.db
# JSON array of Telegram user IDs allowed as ADMIN
ADMIN_TELEGRAM_IDS=[111111111]
INVITE_TTL_SECONDS=86400
LOG_LEVEL=INFO
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_clerk/config.py tests/test_config.py .env.example
git commit -m "feat: typed settings via pydantic-settings"
```

---

## Task 3: Crypto utility (Fernet)

**Files:**
- Create: `src/ai_clerk/crypto.py`
- Test: `tests/test_crypto.py`

- [ ] **Step 1: Write the failing test**

`tests/test_crypto.py`:
```python
import pytest
from cryptography.fernet import InvalidToken

from ai_clerk.crypto import Cipher, generate_key


def test_encrypt_decrypt_roundtrip():
    cipher = Cipher(generate_key())
    token = cipher.encrypt("ИИН 900101300123")
    assert token != "ИИН 900101300123"
    assert cipher.decrypt(token) == "ИИН 900101300123"


def test_wrong_key_cannot_decrypt():
    token = Cipher(generate_key()).encrypt("secret")
    other = Cipher(generate_key())
    with pytest.raises(InvalidToken):
        other.decrypt(token)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_crypto.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.crypto'`

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/crypto.py`:
```python
from cryptography.fernet import Fernet


class Cipher:
    """Symmetric encryption for PII at rest (Fernet)."""

    def __init__(self, key: str | bytes):
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()


def generate_key() -> str:
    """Generate a new urlsafe base64 Fernet key."""
    return Fernet.generate_key().decode()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_crypto.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/crypto.py tests/test_crypto.py
git commit -m "feat: Fernet-based Cipher for PII encryption"
```

---

## Task 4: Role enum + invite tokens

**Files:**
- Create: `src/ai_clerk/roles/__init__.py`
- Create: `src/ai_clerk/roles/enums.py`
- Create: `src/ai_clerk/roles/invites.py`
- Test: `tests/test_invites.py`

- [ ] **Step 1: Write the failing test**

`tests/test_invites.py`:
```python
import pytest

from ai_clerk.roles.enums import Role
from ai_clerk.roles.invites import InviteService, InviteError


def test_generate_and_verify():
    svc = InviteService("secret")
    token = svc.generate(Role.DIRECTOR)
    assert svc.verify(token, max_age_seconds=3600) == Role.DIRECTOR


def test_expired_token_rejected():
    svc = InviteService("secret")
    token = svc.generate(Role.DIRECTOR)
    with pytest.raises(InviteError):
        svc.verify(token, max_age_seconds=-1)


def test_tampered_token_rejected():
    svc = InviteService("secret")
    token = svc.generate(Role.DIRECTOR)
    with pytest.raises(InviteError):
        svc.verify(token + "tamper", max_age_seconds=3600)


def test_wrong_secret_rejected():
    token = InviteService("secret").generate(Role.ADMIN)
    with pytest.raises(InviteError):
        InviteService("other-secret").verify(token, max_age_seconds=3600)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_invites.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.roles'`

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/roles/__init__.py`:
```python
```

`src/ai_clerk/roles/enums.py`:
```python
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    DIRECTOR = "director"
    ACCOUNTANT = "accountant"
```

`src/ai_clerk/roles/invites.py`:
```python
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ai_clerk.roles.enums import Role


class InviteError(Exception):
    """Raised when an invite token is invalid or expired."""


class InviteService:
    """Generates and verifies signed, time-limited role-invite tokens."""

    def __init__(self, secret_key: str, salt: str = "invite"):
        self._serializer = URLSafeTimedSerializer(secret_key, salt=salt)

    def generate(self, role: Role) -> str:
        return self._serializer.dumps({"role": role.value})

    def verify(self, token: str, max_age_seconds: int) -> Role:
        try:
            data = self._serializer.loads(token, max_age=max_age_seconds)
        except SignatureExpired as exc:
            raise InviteError("invite expired") from exc
        except BadSignature as exc:
            raise InviteError("invite invalid") from exc
        return Role(data["role"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_invites.py -v`
Expected: PASS (all 4)

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/roles/__init__.py src/ai_clerk/roles/enums.py src/ai_clerk/roles/invites.py tests/test_invites.py
git commit -m "feat: Role enum and signed invite tokens"
```

---

## Task 5: Database layer (Base, engine, User model) + test fixture

**Files:**
- Create: `src/ai_clerk/db/__init__.py`
- Create: `src/ai_clerk/db/base.py`
- Create: `src/ai_clerk/db/models.py`
- Create: `tests/conftest.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.db'` (and missing `session` fixture)

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/db/__init__.py`:
```python
```

`src/ai_clerk/db/base.py`:
```python
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_engine(database_url: str, **kwargs) -> AsyncEngine:
    return create_async_engine(database_url, future=True, **kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    # Import models so they register on Base.metadata before create_all.
    from ai_clerk.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

`src/ai_clerk/db/models.py`:
```python
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ai_clerk.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True
    )
    chat_id: Mapped[int] = mapped_column(BigInteger)
    role: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`tests/conftest.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/db tests/conftest.py tests/test_db.py
git commit -m "feat: async SQLAlchemy layer with User model and test fixture"
```

---

## Task 6: RoleService

**Files:**
- Create: `src/ai_clerk/roles/service.py`
- Test: `tests/test_role_service.py`

- [ ] **Step 1: Write the failing test**

`tests/test_role_service.py`:
```python
from ai_clerk.roles.enums import Role
from ai_clerk.roles.service import RoleService


async def test_bind_creates_user(session):
    svc = RoleService(session)
    user = await svc.bind_user(telegram_user_id=100, chat_id=100, role=Role.DIRECTOR)
    assert user.id is not None
    assert await svc.get_role(100) == Role.DIRECTOR


async def test_rebind_updates_chat_and_role(session):
    svc = RoleService(session)
    await svc.bind_user(100, 100, Role.DIRECTOR)
    await svc.bind_user(100, 200, Role.ACCOUNTANT)
    assert await svc.get_role(100) == Role.ACCOUNTANT
    user = await svc.get_user(100)
    assert user.chat_id == 200


async def test_update_chat_id(session):
    svc = RoleService(session)
    await svc.bind_user(100, 100, Role.DIRECTOR)
    await svc.update_chat_id(100, 555)
    user = await svc.get_user(100)
    assert user.chat_id == 555


async def test_get_role_unknown_returns_none(session):
    svc = RoleService(session)
    assert await svc.get_role(999) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.roles.service'`

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/roles/service.py`:
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_clerk.db.models import User
from ai_clerk.roles.enums import Role


class RoleService:
    """Binds Telegram users to hardcoded roles and tracks their chat id."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def bind_user(
        self, telegram_user_id: int, chat_id: int, role: Role
    ) -> User:
        user = await self.get_user(telegram_user_id)
        if user is None:
            user = User(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                role=role.value,
            )
            self._session.add(user)
        else:
            user.chat_id = chat_id
            user.role = role.value
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def update_chat_id(self, telegram_user_id: int, chat_id: int) -> None:
        user = await self.get_user(telegram_user_id)
        if user is None:
            return
        user.chat_id = chat_id
        await self._session.commit()

    async def get_role(self, telegram_user_id: int) -> Role | None:
        user = await self.get_user(telegram_user_id)
        return Role(user.role) if user else None

    async def get_user(self, telegram_user_id: int) -> User | None:
        result = await self._session.execute(
            select(User).where(User.telegram_user_id == telegram_user_id)
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_service.py -v`
Expected: PASS (all 4)

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/roles/service.py tests/test_role_service.py
git commit -m "feat: RoleService for binding users to roles"
```

---

## Task 7: Access control (permissions)

**Files:**
- Create: `src/ai_clerk/bot/__init__.py`
- Create: `src/ai_clerk/bot/permissions.py`
- Test: `tests/test_permissions.py`

- [ ] **Step 1: Write the failing test**

`tests/test_permissions.py`:
```python
from ai_clerk.bot.permissions import is_allowed
from ai_clerk.roles.enums import Role


def test_admin_can_invite():
    assert is_allowed(Role.ADMIN, "invite") is True


def test_director_cannot_invite():
    assert is_allowed(Role.DIRECTOR, "invite") is False


def test_director_can_create_trip():
    assert is_allowed(Role.DIRECTOR, "trip.create") is True


def test_accountant_receives_orders():
    assert is_allowed(Role.ACCOUNTANT, "order.receive") is True


def test_unknown_role_denied():
    assert is_allowed(None, "trip.create") is False


def test_unknown_action_denied():
    assert is_allowed(Role.ADMIN, "nonexistent.action") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_permissions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.bot'`

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/bot/__init__.py`:
```python
```

`src/ai_clerk/bot/permissions.py`:
```python
from ai_clerk.roles.enums import Role

ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "invite",
        "trip.create",
        "trip.view",
        "order.receive",
        "profile.edit",
    },
    Role.DIRECTOR: {"trip.create", "trip.view", "profile.edit"},
    Role.ACCOUNTANT: {"order.receive", "trip.view"},
}


def is_allowed(role: Role | None, action: str) -> bool:
    if role is None:
        return False
    return action in ROLE_PERMISSIONS.get(role, set())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_permissions.py -v`
Expected: PASS (all 6)

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/bot/__init__.py src/ai_clerk/bot/permissions.py tests/test_permissions.py
git commit -m "feat: role-based access control map"
```

---

## Task 8: Onboarding logic (handle_start)

**Files:**
- Create: `src/ai_clerk/bot/onboarding.py`
- Test: `tests/test_onboarding.py`

- [ ] **Step 1: Write the failing test**

`tests/test_onboarding.py`:
```python
from ai_clerk.bot.onboarding import handle_start
from ai_clerk.roles.enums import Role
from ai_clerk.roles.invites import InviteService
from ai_clerk.roles.service import RoleService


async def test_valid_token_grants_role(session):
    invites = InviteService("secret")
    roles = RoleService(session)
    token = invites.generate(Role.DIRECTOR)

    reply = await handle_start(token, 10, 10, invites, roles, 3600)

    assert "director" in reply
    assert await roles.get_role(10) == Role.DIRECTOR


async def test_invalid_token_denied(session):
    invites = InviteService("secret")
    roles = RoleService(session)

    reply = await handle_start("garbage", 10, 10, invites, roles, 3600)

    assert "недействительна" in reply
    assert await roles.get_role(10) is None


async def test_no_token_unknown_user(session):
    invites = InviteService("secret")
    roles = RoleService(session)

    reply = await handle_start(None, 5, 5, invites, roles, 3600)

    assert "приглашение" in reply
    assert await roles.get_role(5) is None


async def test_no_token_known_user_refreshes_chat(session):
    invites = InviteService("secret")
    roles = RoleService(session)
    await roles.bind_user(7, 7, Role.ACCOUNTANT)

    reply = await handle_start(None, 7, 999, invites, roles, 3600)

    assert "accountant" in reply
    user = await roles.get_user(7)
    assert user.chat_id == 999
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboarding.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.bot.onboarding'`

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/bot/onboarding.py`:
```python
from ai_clerk.roles.invites import InviteError, InviteService
from ai_clerk.roles.service import RoleService


async def handle_start(
    token: str | None,
    telegram_user_id: int,
    chat_id: int,
    invite_service: InviteService,
    role_service: RoleService,
    invite_ttl_seconds: int,
) -> str:
    """Pure onboarding logic. Returns the reply text to send back."""
    if not token:
        role = await role_service.get_role(telegram_user_id)
        if role is None:
            return (
                "Здравствуйте! Для доступа нужна ссылка-приглашение "
                "от администратора."
            )
        await role_service.update_chat_id(telegram_user_id, chat_id)
        return f"С возвращением! Ваша роль: {role.value}."

    try:
        role = invite_service.verify(token, invite_ttl_seconds)
    except InviteError:
        return "Ссылка-приглашение недействительна или истекла."

    await role_service.bind_user(telegram_user_id, chat_id, role)
    return f"Доступ предоставлен. Ваша роль: {role.value}."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboarding.py -v`
Expected: PASS (all 4)

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/bot/onboarding.py tests/test_onboarding.py
git commit -m "feat: invite-link onboarding logic"
```

---

## Task 9: Admin invite-link builders

**Files:**
- Create: `src/ai_clerk/bot/admin.py`
- Test: `tests/test_admin.py`

- [ ] **Step 1: Write the failing test**

`tests/test_admin.py`:
```python
from ai_clerk.bot.admin import build_invite_link, generate_invite_link
from ai_clerk.roles.enums import Role
from ai_clerk.roles.invites import InviteService


def test_build_invite_link():
    assert build_invite_link("MyBot", "abc") == "https://t.me/MyBot?start=abc"


def test_generate_invite_link_roundtrips_through_verify():
    invites = InviteService("secret")
    link = generate_invite_link("MyBot", Role.ACCOUNTANT, invites)
    token = link.split("start=", 1)[1]
    assert invites.verify(token, max_age_seconds=3600) == Role.ACCOUNTANT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_admin.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.bot.admin'`

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/bot/admin.py`:
```python
from ai_clerk.roles.enums import Role
from ai_clerk.roles.invites import InviteService


def build_invite_link(bot_username: str, token: str) -> str:
    return f"https://t.me/{bot_username}?start={token}"


def generate_invite_link(
    bot_username: str, role: Role, invite_service: InviteService
) -> str:
    token = invite_service.generate(role)
    return build_invite_link(bot_username, token)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin.py -v`
Expected: PASS (both)

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/bot/admin.py tests/test_admin.py
git commit -m "feat: admin invite-link builders"
```

---

## Task 10: aiogram wiring + middleware + entrypoint (manual run verification)

**Files:**
- Create: `src/ai_clerk/bot/middleware.py`
- Create: `src/ai_clerk/bot/main.py`

> This task is glue between aiogram and the tested logic above. It has no unit test; verify by running the bot. All branching logic it calls is already covered by Tasks 6–9.

- [ ] **Step 1: Write the DB-session middleware**

`src/ai_clerk/bot/middleware.py`:
```python
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from ai_clerk.roles.service import RoleService


class DependencyMiddleware(BaseMiddleware):
    """Opens a DB session per update and injects RoleService into handlers."""

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["session"] = session
            data["role_service"] = RoleService(session)
            return await handler(event, data)
```

- [ ] **Step 2: Write the entrypoint with handlers**

`src/ai_clerk/bot/main.py`:
```python
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from ai_clerk.bot.admin import generate_invite_link
from ai_clerk.bot.middleware import DependencyMiddleware
from ai_clerk.bot.onboarding import handle_start
from ai_clerk.bot.permissions import is_allowed
from ai_clerk.config import get_settings
from ai_clerk.db.base import create_engine, create_session_factory, init_models
from ai_clerk.roles.enums import Role
from ai_clerk.roles.invites import InviteService
from ai_clerk.roles.service import RoleService

logger = logging.getLogger(__name__)


def _parse_role(arg: str | None) -> Role | None:
    if not arg:
        return None
    try:
        return Role(arg.strip().lower())
    except ValueError:
        return None


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    engine = create_engine(settings.database_url)
    await init_models(engine)
    session_factory = create_session_factory(engine)

    invite_service = InviteService(settings.secret_key)

    bot = Bot(token=settings.bot_token)
    me = await bot.get_me()
    bot_username = me.username

    dp = Dispatcher()
    dp.update.middleware(DependencyMiddleware(session_factory))

    @dp.message(CommandStart(deep_link=True))
    @dp.message(CommandStart())
    async def on_start(
        message: Message,
        command: CommandObject,
        role_service: RoleService,
    ) -> None:
        token = command.args
        reply = await handle_start(
            token=token,
            telegram_user_id=message.from_user.id,
            chat_id=message.chat.id,
            invite_service=invite_service,
            role_service=role_service,
            invite_ttl_seconds=settings.invite_ttl_seconds,
        )
        await message.answer(reply)

    @dp.message(lambda m: m.text and m.text.startswith("/invite"))
    async def on_invite(
        message: Message,
        command: CommandObject,
        role_service: RoleService,
    ) -> None:
        role = await role_service.get_role(message.from_user.id)
        # Bootstrap: configured admin ids are treated as ADMIN even before binding.
        if role is None and message.from_user.id in settings.admin_telegram_ids:
            role = Role.ADMIN
        if not is_allowed(role, "invite"):
            await message.answer("Недостаточно прав для создания приглашения.")
            return
        target = _parse_role(command.args)
        if target is None:
            await message.answer(
                "Использование: /invite <director|accountant|admin>"
            )
            return
        link = generate_invite_link(bot_username, target, invite_service)
        await message.answer(
            f"Ссылка-приглашение для роли {target.value} (TTL "
            f"{settings.invite_ttl_seconds} c):\n{link}"
        )

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Generate keys and create a local `.env`**

Run:
```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print('FERNET_KEY=' + Fernet.generate_key().decode())"
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
```
Paste the generated values into `.env`, set `BOT_TOKEN` (from @BotFather) and `ADMIN_TELEGRAM_IDS=[<your_telegram_id>]`.

- [ ] **Step 4: Run the bot and verify onboarding end-to-end**

Run: `python -m ai_clerk.bot.main`
Expected console: aiogram start-polling logs, no errors.
Manual check in Telegram:
1. Send `/start` from your admin account → bot replies it needs an invite link (you are not bound yet).
2. Send `/invite director` → bot replies with a `https://t.me/<bot>?start=...` link.
3. Open the link (or `/start <token>`) → bot replies "Доступ предоставлен. Ваша роль: director."
4. Send `/invite director` from a non-admin account → bot replies "Недостаточно прав…".

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests from Tasks 1–9 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_clerk/bot/middleware.py src/ai_clerk/bot/main.py
git commit -m "feat: aiogram wiring with onboarding and admin invite commands"
```

---

## Task 11: Docker & docker-compose

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

> Glue/ops task. Verify with `docker compose config` and (optionally) a container run.

- [ ] **Step 1: Write the Dockerfile**

`Dockerfile`:
```dockerfile
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

CMD ["python", "-m", "ai_clerk.bot.main"]
```

- [ ] **Step 2: Write docker-compose.yml**

`docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ai_clerk
      POSTGRES_PASSWORD: ai_clerk
      POSTGRES_DB: ai_clerk
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ai_clerk"]
      interval: 5s
      timeout: 3s
      retries: 5

  bot:
    build: .
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://ai_clerk:ai_clerk@db:5432/ai_clerk
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

- [ ] **Step 3: Validate the compose file**

Run: `docker compose config`
Expected: prints the resolved config with no errors.

- [ ] **Step 4: (Optional) Build and run**

Run: `docker compose up --build`
Expected: `db` becomes healthy, `bot` starts polling (requires a valid `.env` with `BOT_TOKEN`).

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "chore: containerize bot with postgres via docker-compose"
```

---

## Self-Review

**Spec coverage (Plan 1 scope — spec §2, §3 items 1/8/11/12, §5 partial, §6 partial):**
- Stack Python 3.14 + aiogram → Tasks 1, 10. ✓
- Telegram Gateway (component 1) → Task 10. ✓
- RoleService / AccessControl (component 8) → Tasks 6, 7. ✓
- Invite-link onboarding (spec §5) → Tasks 4, 8, 9, 10. ✓
- Index/DB foundation (component 11) → Task 5 (User table; trip/profile tables come in later plans). ✓
- Crypto/Secrets (component 12) → Task 3 (Cipher ready; applied to PII in Plan 2). ✓
- Docker deploy (spec §9) → Task 11. ✓
- Deferred to later plans (correctly out of scope here): Orchestrator, Trip Saga, BookingProvider, Browser-Agent, OrderService, ProfileService, LocationService, TripArchive containers. These are Plans 2–5.

**Placeholder scan:** No TBD/TODO/"handle edge cases". Empty `__init__.py` files are intentionally empty (shown as empty code blocks). ✓

**Type consistency:** `Role` (str enum) used consistently; `RoleService` methods (`bind_user`, `update_chat_id`, `get_role`, `get_user`) match across Tasks 6, 8, 10; `InviteService.generate/verify`, `is_allowed`, `handle_start`, `generate_invite_link/build_invite_link` signatures match their call sites. ✓
