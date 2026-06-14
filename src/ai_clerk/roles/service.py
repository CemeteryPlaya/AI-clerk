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
