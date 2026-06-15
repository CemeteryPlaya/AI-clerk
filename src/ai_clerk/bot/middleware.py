from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from ai_clerk.roles.invites import InviteService
from ai_clerk.roles.service import RoleService


class DependencyMiddleware(BaseMiddleware):
    """Opens a DB session per update and injects services into handlers."""

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
            data["invite_service"] = InviteService(session)
            return await handler(event, data)
