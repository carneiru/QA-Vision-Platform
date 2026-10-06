from jwt import InvalidTokenError, decode

from src.project.core.config import settings


def decode_token(token: str) -> dict:
    try:
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise ValueError("Could not validate credentials")
    # auth-service signs refresh tokens with the same key and `sub`; only `token_type` tells them
    # apart. Refresh tokens are long-lived and must not reach the API.
    if payload.get("token_type") == "refresh":
        raise ValueError("refresh tokens cannot be used for API access")
    return payload


def is_access_token(claims: dict) -> bool:
    """A user access token carries neither `purpose` (MFA challenge, and any future single-use token)
    nor `token_type` (refresh, service). auth-service signs all of them with the same key and `sub`,
    so only the absence of these claims says "this is a user session"."""
    return "purpose" not in claims and "token_type" not in claims
