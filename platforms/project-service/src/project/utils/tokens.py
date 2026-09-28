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
