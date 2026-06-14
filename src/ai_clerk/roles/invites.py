from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ai_clerk.roles.enums import Role


class InviteError(Exception):
    """Raised when an invite token is invalid or expired."""


class InviteService:
    """Generates and verifies signed, time-limited role-invite tokens."""

    def __init__(self, secret_key: str, salt: str = "invite"):
        self._serializer = URLSafeTimedSerializer(secret_key, salt=salt)

    def generate(self, role: Role) -> str:
        return self._serializer.dumps({"role": role.value})

    def verify(self, token: str, max_age_seconds: int) -> Role:
        try:
            data = self._serializer.loads(token, max_age=max_age_seconds)
        except SignatureExpired as exc:
            raise InviteError("invite expired") from exc
        except BadSignature as exc:
            raise InviteError("invite invalid") from exc
        return Role(data["role"])
