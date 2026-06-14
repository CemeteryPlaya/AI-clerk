import pytest
from cryptography.fernet import InvalidToken

from ai_clerk.crypto import Cipher, generate_key


def test_encrypt_decrypt_roundtrip():
    cipher = Cipher(generate_key())
    token = cipher.encrypt("ИИН 900101300123")
    assert token != "ИИН 900101300123"
    assert cipher.decrypt(token) == "ИИН 900101300123"


def test_wrong_key_cannot_decrypt():
    token = Cipher(generate_key()).encrypt("secret")
    other = Cipher(generate_key())
    with pytest.raises(InvalidToken):
        other.decrypt(token)
