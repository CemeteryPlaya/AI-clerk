import secrets
import time

from sqlalchemy.ext.asyncio import AsyncSession

from ai_clerk.db.models import PendingInvite
from ai_clerk.roles.enums import Role


class InviteError(Exception):
    """Raised when an invite token is invalid or expired."""


class InviteService:
    """Issues and consumes opaque, single-use, time-limited role invites.

    Tokens are random url-safe strings (Telegram deep-link safe: only
    [A-Za-z0-9_-], <= 64 chars) persisted in the pending_invites table.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def generate(self, role: Role) -> str:
        token = secrets.token_urlsafe(32)
        self._session.add(
            PendingInvite(token=token, role=role.value, created_at=time.time())
        )
        await self._session.commit()
        return token

    async def verify(self, token: str, max_age_seconds: int) -> Role:
        invite = await self._session.get(PendingInvite, token)
        if invite is None:
            raise InviteError("invite invalid")
        age = time.time() - invite.created_at
        role_value = invite.role
        await self._session.delete(invite)  # single-use
        await self._session.commit()
        if age > max_age_seconds:
            raise InviteError("invite expired")
        return Role(role_value)
