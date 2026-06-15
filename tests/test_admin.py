from ai_clerk.bot.admin import build_invite_link, generate_invite_link
from ai_clerk.roles.enums import Role
from ai_clerk.roles.invites import InviteService


def test_build_invite_link():
    assert build_invite_link("MyBot", "abc") == "https://t.me/MyBot?start=abc"


async def test_generate_invite_link_roundtrips_through_verify(session):
    invites = InviteService(session)
    link = await generate_invite_link("MyBot", Role.ACCOUNTANT, invites)
    token = link.split("start=", 1)[1]
    assert await invites.verify(token, max_age_seconds=3600) == Role.ACCOUNTANT
