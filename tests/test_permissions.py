from ai_clerk.bot.permissions import is_allowed
from ai_clerk.roles.enums import Role


def test_admin_can_invite():
    assert is_allowed(Role.ADMIN, "invite") is True


def test_director_cannot_invite():
    assert is_allowed(Role.DIRECTOR, "invite") is False


def test_director_can_create_trip():
    assert is_allowed(Role.DIRECTOR, "trip.create") is True


def test_accountant_receives_orders():
    assert is_allowed(Role.ACCOUNTANT, "order.receive") is True


def test_unknown_role_denied():
    assert is_allowed(None, "trip.create") is False


def test_unknown_action_denied():
    assert is_allowed(Role.ADMIN, "nonexistent.action") is False
