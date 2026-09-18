import httpx
import pytest
import respx
from src.organization.core.config import settings
from src.organization.utils.auth_client import user_exists, AuthServiceUnavailable


@respx.mock
def test_user_exists_true_on_200():
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/7").mock(
        return_value=httpx.Response(200, json={"id": 7, "email": "a@b.com"})
    )
    assert user_exists(7) is True


@respx.mock
def test_user_exists_false_on_404():
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/999").mock(return_value=httpx.Response(404))
    assert user_exists(999) is False


@respx.mock
def test_user_exists_raises_on_timeout():
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/7").mock(side_effect=httpx.ConnectTimeout("timeout"))
    with pytest.raises(AuthServiceUnavailable):
        user_exists(7)
