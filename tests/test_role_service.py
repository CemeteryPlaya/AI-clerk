from ai_clerk.roles.enums import Role
from ai_clerk.roles.service import RoleService


async def test_bind_creates_user(session):
    svc = RoleService(session)
    user = await svc.bind_user(telegram_user_id=100, chat_id=100, role=Role.DIRECTOR)
    assert user.id is not None
    assert await svc.get_role(100) == Role.DIRECTOR


async def test_rebind_updates_chat_and_role(session):
    svc = RoleService(session)
    await svc.bind_user(100, 100, Role.DIRECTOR)
    await svc.bind_user(100, 200, Role.ACCOUNTANT)
    assert await svc.get_role(100) == Role.ACCOUNTANT
    user = await svc.get_user(100)
    assert user.chat_id == 200


async def test_update_chat_id(session):
    svc = RoleService(session)
    await svc.bind_user(100, 100, Role.DIRECTOR)
    await svc.update_chat_id(100, 555)
    user = await svc.get_user(100)
    assert user.chat_id == 555


async def test_get_role_unknown_returns_none(session):
    svc = RoleService(session)
    assert await svc.get_role(999) is None
