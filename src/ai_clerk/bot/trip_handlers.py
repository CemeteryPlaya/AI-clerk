import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ai_clerk.bot.permissions import is_allowed
from ai_clerk.profile.service import ProfileService
from ai_clerk.roles.service import RoleService
from ai_clerk.trips.orchestrator import Orchestrator
from ai_clerk.trips.presentation import render_flight_options
from ai_clerk.trips.service import TripService

logger = logging.getLogger(__name__)


def build_trip_router(orchestrator: Orchestrator) -> Router:
    router = Router()

    async def _can_create(message: Message, role_service: RoleService) -> bool:
        if message.from_user is None:
            return False
        role = await role_service.get_role(message.from_user.id)
        return is_allowed(role, "trip.create")

    @router.message(Command("cancel"))
    async def on_cancel(message: Message, role_service: RoleService) -> None:
        if not await _can_create(message, role_service):
            return
        orchestrator.cancel(message.chat.id)
        await message.answer("Текущий запрос на поездку сброшен.")

    @router.message(F.text & ~F.text.startswith("/"))
    async def on_text(
        message: Message,
        role_service: RoleService,
        profile_service: ProfileService,
    ) -> None:
        if not await _can_create(message, role_service):
            return  # ignore free text from users without trip.create
        profile = await profile_service.get_profile(message.from_user.id)
        try:
            reply = await orchestrator.handle_message(
                message.chat.id, message.text, profile
            )
        except Exception:
            logger.exception("Orchestrator failed for chat %s", message.chat.id)
            await message.answer(
                "Не смог обработать запрос. Попробуйте сформулировать ещё раз."
            )
            return
        if reply.flights:
            text, keyboard = render_flight_options(reply.flights)
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(reply.text)

    @router.callback_query(F.data.startswith("trip:pick:"))
    async def on_pick(
        callback: CallbackQuery,
        session: AsyncSession,
        profile_service: ProfileService,
    ) -> None:
        if callback.message is None:
            await callback.answer(
                "Сессия устарела, начните поиск заново.", show_alert=True
            )
            return
        index = int(callback.data.rsplit(":", 1)[1])
        profile = await profile_service.get_profile(callback.from_user.id)
        draft = await orchestrator.pick(callback.message.chat.id, index, profile)
        if draft is None:
            await callback.answer(
                "Вариант недоступен, начните поиск заново.", show_alert=True
            )
            return
        trip = await TripService(session).create_confirmed_trip(
            callback.message.chat.id, callback.from_user.id, draft
        )
        flight = draft.flight
        hotel_line = (
            f"\nОтель: {draft.hotel.name} {draft.hotel.stars}★, "
            f"{int(draft.hotel.total_price)} ₸"
            if draft.hotel
            else ""
        )
        text = (
            f"Вариант выбран (поездка #{trip.id}).\n"
            f"Рейс: {flight.airline} {flight.departure:%d.%m %H:%M}→{flight.arrival:%H:%M}, "
            f"{int(flight.price)} ₸.{hotel_line}\n"
            "Бронирование и оплата — на следующем шаге."
        )
        # callback.message may be an InaccessibleMessage on very old callbacks;
        # only a real Message can be edited in place.
        if isinstance(callback.message, Message):
            await callback.message.edit_text(text)
            await callback.answer()
        else:
            await callback.answer(text, show_alert=True)

    return router
