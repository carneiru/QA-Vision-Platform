import httpx
import pytest

from src.project.utils import org_client


def test_returns_the_role_and_forwards_only_the_callers_token(org_role):
    route = org_role("admin", org_id=7)
    assert org_client.get_my_role(7, "caller-token") == "admin"
    assert route.calls.last.request.headers["Authorization"] == "Bearer caller-token"


def test_404_is_not_a_member(org_role):
    org_role(org_id=7, status_code=404, body={"detail": "Not a member of this organization"})
    with pytest.raises(org_client.NotAMember):
        org_client.get_my_role(7, "t")


def test_401_is_invalid_credentials(org_role):
    org_role(org_id=7, status_code=401, body={"detail": "Could not validate credentials"})
    with pytest.raises(org_client.InvalidCredentials):
        org_client.get_my_role(7, "t")


@pytest.mark.parametrize("status_code", [403, 500, 502, 503])
def test_other_statuses_are_unavailable(org_role, status_code):
    org_role(org_id=7, status_code=status_code, body={"detail": "x"})
    with pytest.raises(org_client.OrgServiceUnavailable):
        org_client.get_my_role(7, "t")


def test_timeout_is_unavailable(org_role):
    org_role(org_id=7, exc=httpx.ReadTimeout("slow"))
    with pytest.raises(org_client.OrgServiceUnavailable):
        org_client.get_my_role(7, "t")


def test_connection_error_is_unavailable(org_role):
    org_role(org_id=7, exc=httpx.ConnectError("refused"))
    with pytest.raises(org_client.OrgServiceUnavailable):
        org_client.get_my_role(7, "t")


@pytest.mark.parametrize(
    "body",
    [
        {"role": "superuser"},                   # not one of the five roles
        {"role": "admin", "extra": True},        # not exactly one key
        {"member_role": "admin"},                # renamed key
        ["admin"],                               # not an object
    ],
)
def test_200_outside_the_contract_is_unavailable(org_role, body):
    org_role(org_id=7, body=body)
    with pytest.raises(org_client.OrgServiceUnavailable):
        org_client.get_my_role(7, "t")


def test_200_with_non_json_body_is_unavailable(http):
    from src.project.core.config import settings

    http.get(
        f"{settings.ORGANIZATION_SERVICE_URL}/api/v1/organizations/7/members/me", name="org-me-7"
    ).mock(return_value=httpx.Response(200, text="<html>oops</html>"))
    with pytest.raises(org_client.OrgServiceUnavailable):
        org_client.get_my_role(7, "t")


def test_a_trailing_slash_in_the_configured_url_does_not_double_up(http, monkeypatch):
    from src.project.core.config import settings

    monkeypatch.setattr(settings, "ORGANIZATION_SERVICE_URL", "http://orgs.test/")
    route = http.get("http://orgs.test/api/v1/organizations/7/members/me", name="org-me-7-trailing-slash").mock(
        return_value=httpx.Response(200, json={"role": "admin"})
    )
    assert org_client.get_my_role(7, "t") == "admin"
    assert route.called
