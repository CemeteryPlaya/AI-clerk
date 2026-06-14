from cryptography.fernet import Fernet


class Cipher:
    """Symmetric encryption for PII at rest (Fernet)."""

    def __init__(self, key: str | bytes):
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()


def generate_key() -> str:
    """Generate a new urlsafe base64 Fernet key."""
    return Fernet.generate_key().decode()
