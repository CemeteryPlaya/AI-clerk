import pytest

from ai_clerk.roles.enums import Role
from ai_clerk.roles.invites import InviteService, InviteError


def test_generate_and_verify():
    svc = InviteService("secret")
    token = svc.generate(Role.DIRECTOR)
    assert svc.verify(token, max_age_seconds=3600) == Role.DIRECTOR


def test_expired_token_rejected():
    svc = InviteService("secret")
    token = svc.generate(Role.DIRECTOR)
    with pytest.raises(InviteError):
        svc.verify(token, max_age_seconds=-1)


def test_tampered_token_rejected():
    svc = InviteService("secret")
    token = svc.generate(Role.DIRECTOR)
    with pytest.raises(InviteError):
        svc.verify(token + "tamper", max_age_seconds=3600)


def test_wrong_secret_rejected():
    token = InviteService("secret").generate(Role.ADMIN)
    with pytest.raises(InviteError):
        InviteService("other-secret").verify(token, max_age_seconds=3600)
