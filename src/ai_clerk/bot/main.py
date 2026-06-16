import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from ai_clerk.bot.admin import generate_invite_link
from ai_clerk.bot.middleware import DependencyMiddleware
from ai_clerk.bot.onboarding import handle_start
from ai_clerk.bot.permissions import is_allowed
from ai_clerk.bot.profile_handlers import build_profile_router
from ai_clerk.config import get_settings
from ai_clerk.crypto import Cipher
from ai_clerk.db.base import create_engine, create_session_factory, init_models
from ai_clerk.location.airports import AirportIndex
from ai_clerk.location.service import LocationService
from ai_clerk.profile.extraction.fields import RegexProfileExtractor
from ai_clerk.profile.extraction.ocr import TesseractOcrEngine
from ai_clerk.profile.extraction.pdf_text import PdfTextExtractor
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
    cipher = Cipher(settings.fernet_key)
    location_service = LocationService(AirportIndex.bundled())
    pdf_extractor = PdfTextExtractor(TesseractOcrEngine())
    field_extractor = RegexProfileExtractor()

    bot = Bot(token=settings.bot_token)
    me = await bot.get_me()
    if me.username is None:
        raise RuntimeError("Bot must have a @username to use invite links")
    bot_username = me.username

    dp = Dispatcher()
    dp.update.middleware(DependencyMiddleware(session_factory, cipher))

    @dp.message(CommandStart())
    async def on_start(
        message: Message,
        command: CommandObject,
        role_service: RoleService,
        invite_service: InviteService,
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

    @dp.message(Command("invite"))
    async def on_invite(
        message: Message,
        command: CommandObject,
        role_service: RoleService,
        invite_service: InviteService,
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
        if (
            target is Role.ADMIN
            and message.from_user.id not in settings.admin_telegram_ids
        ):
            await message.answer("Создавать роль ADMIN могут только основатели.")
            return
        link = await generate_invite_link(bot_username, target, invite_service)
        await message.answer(
            f"Ссылка-приглашение для роли {target.value} (TTL "
            f"{settings.invite_ttl_seconds}с):\n{link}"
        )

    dp.include_router(
        build_profile_router(location_service, pdf_extractor, field_extractor)
    )

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
