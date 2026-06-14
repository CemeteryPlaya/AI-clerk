from ai_clerk.roles.enums import Role

ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "invite",
        "trip.create",
        "trip.view",
        "order.receive",
        "profile.edit",
    },
    Role.DIRECTOR: {"trip.create", "trip.view", "profile.edit"},
    Role.ACCOUNTANT: {"order.receive", "trip.view"},
}


def is_allowed(role: Role | None, action: str) -> bool:
    if role is None:
        return False
    return action in ROLE_PERMISSIONS.get(role, set())
