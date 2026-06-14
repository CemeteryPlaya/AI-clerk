from ai_clerk.roles.enums import Role
from ai_clerk.roles.invites import InviteService


def build_invite_link(bot_username: str, token: str) -> str:
    return f"https://t.me/{bot_username}?start={token}"


def generate_invite_link(
    bot_username: str, role: Role, invite_service: InviteService
) -> str:
    token = invite_service.generate(role)
    return build_invite_link(bot_username, token)
