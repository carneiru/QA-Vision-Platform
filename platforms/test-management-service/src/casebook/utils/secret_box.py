"""The GitHub token at rest: Fernet with TM_SECRETS_KEY. Nothing here logs or returns the plain token."""
from cryptography.fernet import Fernet, InvalidToken

from src.casebook.core.config import settings

NOT_CONFIGURED = "Running tests from QEOS is not configured on this server"
UNREADABLE = "The stored GitHub token cannot be read with this server's key: replace it in Settings"


class SecretsUnavailable(Exception):
    """No usable TM_SECRETS_KEY, or a stored token sealed with another key."""


def _fernet() -> Fernet:
    key = settings.TM_SECRETS_KEY.strip()
    if not key:
        raise SecretsUnavailable(NOT_CONFIGURED)
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise SecretsUnavailable(NOT_CONFIGURED) from None


def is_available() -> bool:
    try:
        _fernet()
    except SecretsUnavailable:
        return False
    return True


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str:
    box = _fernet()
    try:
        return box.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):  # incl. UnicodeEncodeError/UnicodeDecodeError
        raise SecretsUnavailable(UNREADABLE) from None
