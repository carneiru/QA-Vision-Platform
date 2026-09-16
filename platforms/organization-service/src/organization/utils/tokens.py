from jwt import decode, InvalidTokenError
from src.organization.core.config import settings


def decode_token(token: str) -> dict:
    try:
        return decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise ValueError("Could not validate credentials")
