"""The refresh token's httpOnly cookie: set on every endpoint that issues a
token pair, cleared on logout. Scoped to the auth endpoints so no other
request ever carries it."""

from fastapi import Response

from src.auth.config import settings

REFRESH_COOKIE = "qav_refresh"
COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=True,
        samesite="strict",
        path=COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
