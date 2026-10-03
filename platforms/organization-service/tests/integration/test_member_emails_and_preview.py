"""Member listings carry emails (batch internal lookup, best effort) and an
authenticated invitee can preview an invitation before accepting it."""
import httpx
import jwt
import respx
from datetime import datetime, timedelta, timezone

from src.organization.core.config import settings


def _token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _auth(user_id: int) -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _make_org(client, owner_id: int) -> int:
    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme", "slug": "acme", "plan_tier": "free"},
        headers=_auth(owner_id),
    )
    return response.json()["id"]


BATCH = f"{settings.AUTH_SERVICE_URL}/internal/v1/users"


@respx.mock
def test_member_list_carries_emails(client):
    org_id = _make_org(client, owner_id=1)
    respx.get(BATCH, params={"ids": "1"}).mock(
        return_value=httpx.Response(200, json={"users": [
            {"id": 1, "email": "owner@example.com", "is_active": True},
        ]})
    )

    response = client.get(f"/api/v1/organizations/{org_id}/members", headers=_auth(1))
    assert response.status_code == 200, response.text
    assert response.json()[0]["email"] == "owner@example.com"


@respx.mock
def test_member_list_survives_auth_service_being_down(client):
    org_id = _make_org(client, owner_id=1)
    respx.get(BATCH, params={"ids": "1"}).mock(side_effect=httpx.ConnectError("refused"))

    response = client.get(f"/api/v1/organizations/{org_id}/members", headers=_auth(1))
    assert response.status_code == 200, response.text
    assert response.json()[0]["email"] is None


def _invite(client, org_id: int, email="carol@example.com") -> str:
    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": email, "role": "member"},
        headers=_auth(1),
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


def test_preview_names_the_organization_and_role(client):
    org_id = _make_org(client, owner_id=1)
    token = _invite(client, org_id)

    response = client.get(f"/api/v1/invitations/{token}", headers=_auth(5))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "organization_id": org_id,
        "organization_name": "Acme",
        "email": "carol@example.com",
        "role": "member",
        "expires_at": body["expires_at"],
    }


@respx.mock
def test_preview_of_a_dead_or_unknown_token_is_404(client):
    org_id = _make_org(client, owner_id=1)
    token = _invite(client, org_id)
    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/6").mock(
        return_value=httpx.Response(200, json={"id": 6, "email": "e", "is_active": True}))
    accepted = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(6))
    assert accepted.status_code == 201

    assert client.get(f"/api/v1/invitations/{token}", headers=_auth(7)).status_code == 404
    assert client.get("/api/v1/invitations/no-such-token", headers=_auth(7)).status_code == 404


def test_preview_needs_authentication(client):
    org_id = _make_org(client, owner_id=1)
    token = _invite(client, org_id)
    assert client.get(f"/api/v1/invitations/{token}").status_code == 401
