"""The refresh token's httpOnly cookie: set on every endpoint that issues a
token pair, cleared on logout. Scoped to the auth endpoints so no other
request ever carries it.

The cookie was called `qav_refresh` before the QEOS rename. It is still read as a
fallback so nobody is logged out by the rename; a refresh that used it reissues the
new cookie and clears the old one, and logout clears both. Every token issue also clears a
stale old cookie, and logout revokes the session behind each cookie it receives."""

from typing import Optional

from fastapi import Request, Response

from src.auth.config import settings

REFRESH_COOKIE = "qeos_refresh"
LEGACY_REFRESH_COOKIE = "qav_refresh"
COOKIE_PATH = "/api/v1/auth"


def read_refresh_cookie(request: Request) -> tuple[Optional[str], bool]:
    """The presented cookie token, and whether it came from the legacy cookie."""
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        return token, False
    legacy = request.cookies.get(LEGACY_REFRESH_COOKIE)
    return legacy, bool(legacy)


def legacy_refresh_cookie(request: Request) -> Optional[str]:
    return request.cookies.get(LEGACY_REFRESH_COOKIE) or None


def set_refresh_cookie(response: Response, token: str) -> None:
    """Sets the new cookie and clears a stale pre-rename one, on every token issue."""
    clear_legacy_refresh_cookie(response)
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=True,
        samesite="strict",
        path=COOKIE_PATH,
    )


def clear_legacy_refresh_cookie(response: Response) -> None:
    response.delete_cookie(LEGACY_REFRESH_COOKIE, path=COOKIE_PATH)


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    clear_legacy_refresh_cookie(response)
