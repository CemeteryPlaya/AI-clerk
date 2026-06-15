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
        role = await invite_service.verify(token, invite_ttl_seconds)
    except InviteError:
        return "Ссылка-приглашение недействительна или истекла."

    await role_service.bind_user(telegram_user_id, chat_id, role)
    return f"Доступ предоставлен. Ваша роль: {role.value}."
