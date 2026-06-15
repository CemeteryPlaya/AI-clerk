import re

import pytest

from ai_clerk.roles.enums import Role
from ai_clerk.roles.invites import InviteError, InviteService


async def test_generate_and_verify(session):
    svc = InviteService(session)
    token = await svc.generate(Role.DIRECTOR)
    assert await svc.verify(token, max_age_seconds=3600) == Role.DIRECTOR


async def test_token_is_telegram_deeplink_safe(session):
    svc = InviteService(session)
    token = await svc.generate(Role.DIRECTOR)
    # Telegram deep-link start payload: only [A-Za-z0-9_-], max 64 chars.
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", token)


async def test_token_is_single_use(session):
    svc = InviteService(session)
    token = await svc.generate(Role.DIRECTOR)
    assert await svc.verify(token, max_age_seconds=3600) == Role.DIRECTOR
    with pytest.raises(InviteError):
        await svc.verify(token, max_age_seconds=3600)


async def test_expired_token_rejected(session):
    svc = InviteService(session)
    token = await svc.generate(Role.DIRECTOR)
    with pytest.raises(InviteError):
        await svc.verify(token, max_age_seconds=-1)


async def test_unknown_token_rejected(session):
    svc = InviteService(session)
    with pytest.raises(InviteError):
        await svc.verify("nonexistent-token", max_age_seconds=3600)
