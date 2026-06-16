import io
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from ai_clerk.bot.permissions import is_allowed
from ai_clerk.location.service import LocationService
from ai_clerk.profile.dto import ProfileDTO
from ai_clerk.profile.extraction.fields import ExtractedProfile, ProfileExtractor
from ai_clerk.profile.extraction.pdf_text import PdfTextExtractor
from ai_clerk.profile.masking import mask_document, mask_iin
from ai_clerk.profile.service import ProfileService
from ai_clerk.roles.service import RoleService

logger = logging.getLogger(__name__)


def _profile_summary(dto: ProfileDTO | None) -> str:
    if dto is None:
        return (
            "Профиль пуст. Пришлите PDF-документ с вашими данными "
            "(паспорт/удостоверение) — я распознаю их локально."
        )
    departure = dto.default_departure_city or dto.default_departure_iata or "—"
    return (
        "Ваш профиль:\n"
        f"• ФИО: {dto.full_name or '—'}\n"
        f"• ИИН: {mask_iin(dto.iin)}\n"
        f"• Документ: {dto.document_type or '—'} {mask_document(dto.document_number)}\n"
        f"• Должность: {dto.position or '—'}\n"
        f"• Город вылета по умолчанию: {departure}\n\n"
        "Чтобы обновить личные данные — пришлите PDF-документ. "
        "Чтобы задать город вылета — /location."
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сохранить", callback_data="profile:save"),
                InlineKeyboardButton(text="Загрузить заново", callback_data="profile:redo"),
            ]
        ]
    )


def _masked_confirmation(extracted: ExtractedProfile) -> str:
    return (
        "Распознал данные (показаны маскированно):\n"
        f"• ФИО: {extracted.full_name or '—'}\n"
        f"• ИИН: {mask_iin(extracted.iin)}\n"
        f"• № документа: {mask_document(extracted.document_number)}\n"
        f"• Дата рождения: {extracted.birth_date or '—'}\n\n"
        "Сохранить в зашифрованном виде?"
    )


def build_profile_router(
    location_service: LocationService,
    pdf_extractor: PdfTextExtractor,
    field_extractor: ProfileExtractor,
) -> Router:
    router = Router()
    # Per-user pending extraction, awaiting confirmation (in-memory, single-process).
    # TODO: move to a DB/Redis-backed store with TTL eviction once a second
    # process (worker/scheduler) exists or the bot runs multi-instance.
    pending: dict[int, ExtractedProfile] = {}

    async def _ensure_can_edit(message: Message, role_service: RoleService) -> bool:
        if message.from_user is None:
            return False
        role = await role_service.get_role(message.from_user.id)
        if not is_allowed(role, "profile.edit"):
            await message.answer("Недостаточно прав для редактирования профиля.")
            return False
        return True

    @router.message(Command("profile"))
    async def on_profile(
        message: Message,
        role_service: RoleService,
        profile_service: ProfileService,
    ) -> None:
        if not await _ensure_can_edit(message, role_service):
            return
        dto = await profile_service.get_profile(message.from_user.id)
        await message.answer(_profile_summary(dto))

    @router.message(F.document & (F.document.mime_type == "application/pdf"))
    async def on_document(
        message: Message,
        role_service: RoleService,
    ) -> None:
        if not await _ensure_can_edit(message, role_service):
            return
        file = await message.bot.get_file(message.document.file_id)
        buffer = io.BytesIO()
        await message.bot.download(file, destination=buffer)
        try:
            text = pdf_extractor.extract_text(buffer.getvalue())
            extracted = field_extractor.extract(text)
        except Exception:
            logger.exception(
                "PDF extraction failed for user %s", message.from_user.id
            )
            await message.answer(
                "Не удалось прочитать документ. Убедитесь, что файл не повреждён, "
                "и попробуйте снова."
            )
            return
        pending[message.from_user.id] = extracted
        await message.answer(_masked_confirmation(extracted), reply_markup=_confirm_keyboard())

    @router.message(F.document)
    async def on_non_pdf_document(message: Message) -> None:
        await message.answer("Пожалуйста, пришлите документ в формате PDF.")

    @router.callback_query(F.data == "profile:save")
    async def on_save(
        callback: CallbackQuery,
        profile_service: ProfileService,
    ) -> None:
        extracted = pending.pop(callback.from_user.id, None)
        if extracted is None:
            await callback.answer("Нет данных для сохранения.", show_alert=True)
            return
        await profile_service.upsert_identity(
            callback.from_user.id,
            full_name=extracted.full_name,
            iin=extracted.iin,
            document_number=extracted.document_number,
            birth_date=extracted.birth_date,
        )
        await callback.message.edit_text("Данные сохранены в зашифрованном виде.")
        await callback.answer()

    @router.callback_query(F.data == "profile:redo")
    async def on_redo(callback: CallbackQuery) -> None:
        pending.pop(callback.from_user.id, None)
        await callback.message.edit_text("Хорошо, пришлите PDF-документ заново.")
        await callback.answer()

    @router.message(Command("location"))
    async def on_location_prompt(
        message: Message,
        role_service: RoleService,
    ) -> None:
        if not await _ensure_can_edit(message, role_service):
            return
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📍 Поделиться геопозицией", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.answer(
            "Поделитесь геопозицией — найду ближайший аэропорт.",
            reply_markup=keyboard,
        )

    @router.message(F.location)
    async def on_location(
        message: Message,
        role_service: RoleService,
        profile_service: ProfileService,
    ) -> None:
        if not await _ensure_can_edit(message, role_service):
            return
        resolution = location_service.resolve_departure(
            coords=(message.location.latitude, message.location.longitude)
        )
        if resolution is None:
            await message.answer("Не удалось определить ближайший аэропорт.")
            return
        airport = resolution.airport
        await profile_service.set_default_departure(
            message.from_user.id, iata=airport.iata, city=airport.city
        )
        await message.answer(
            f"Ближайший аэропорт: {airport.name} ({airport.iata}). "
            "Запомнил как город вылета по умолчанию."
        )

    return router
