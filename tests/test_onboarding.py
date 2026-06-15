from ai_clerk.bot.onboarding import handle_start
from ai_clerk.roles.enums import Role
from ai_clerk.roles.invites import InviteService
from ai_clerk.roles.service import RoleService


async def test_valid_token_grants_role(session):
    invites = InviteService(session)
    roles = RoleService(session)
    token = await invites.generate(Role.DIRECTOR)

    reply = await handle_start(token, 10, 10, invites, roles, 3600)

    assert "director" in reply
    assert await roles.get_role(10) == Role.DIRECTOR


async def test_invalid_token_denied(session):
    invites = InviteService(session)
    roles = RoleService(session)

    reply = await handle_start("garbage", 10, 10, invites, roles, 3600)

    assert "недействительна" in reply
    assert await roles.get_role(10) is None


async def test_no_token_unknown_user(session):
    invites = InviteService(session)
    roles = RoleService(session)

    reply = await handle_start(None, 5, 5, invites, roles, 3600)

    assert "приглашение" in reply
    assert await roles.get_role(5) is None


async def test_no_token_known_user_refreshes_chat(session):
    invites = InviteService(session)
    roles = RoleService(session)
    await roles.bind_user(7, 7, Role.ACCOUNTANT)

    reply = await handle_start(None, 7, 999, invites, roles, 3600)

    assert "accountant" in reply
    user = await roles.get_user(7)
    assert user.chat_id == 999
