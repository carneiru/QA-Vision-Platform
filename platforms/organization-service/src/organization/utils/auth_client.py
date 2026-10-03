import httpx
from src.organization.core.config import settings


class AuthServiceUnavailable(Exception):
    """Raised when auth-service cannot be reached to validate a user_id."""


def user_exists(user_id: int) -> bool:
    """Asks auth-service's internal API (HTTP Basic, shared secret). A clean
    404 means the user does not exist; anything but 200/404 — including an
    unconfigured internal API answering 503 — is unavailability, never a
    silent yes or no."""
    try:
        response = httpx.get(
            f"{settings.AUTH_SERVICE_URL}/internal/v1/users/{user_id}",
            auth=(settings.INTERNAL_API_USERNAME, settings.INTERNAL_API_PASSWORD),
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise AuthServiceUnavailable(f"Could not reach auth-service: {exc}") from exc

    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    raise AuthServiceUnavailable(f"Unexpected auth-service response: {response.status_code}")
