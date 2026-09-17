import httpx
from src.organization.core.config import settings


class AuthServiceUnavailable(Exception):
    """Raised when auth-service cannot be reached to validate a user_id."""


# Known limitation: this assumes auth-service returns 404 for a nonexistent user id, which it does not
# currently do cleanly; fixing it requires changes in platforms/auth-service and is a documented follow-up.
def user_exists(user_id: int) -> bool:
    headers = {"Authorization": f"Bearer {settings.AUTH_SERVICE_TOKEN}"} if settings.AUTH_SERVICE_TOKEN else {}
    try:
        response = httpx.get(
            f"{settings.AUTH_SERVICE_URL}/api/v1/users/{user_id}",
            headers=headers,
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise AuthServiceUnavailable(f"Could not reach auth-service: {exc}") from exc

    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    raise AuthServiceUnavailable(f"Unexpected auth-service response: {response.status_code}")
