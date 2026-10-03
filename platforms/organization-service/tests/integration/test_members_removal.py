"""Role hierarchy / last-owner guards on member removal, and soft-deleted-org isolation."""
import jwt
import respx
import httpx
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
    assert response.status_code == 201
    return response.json()["id"]


def _add_member(client, org_id: int, granter_id: int, user_id: int, role: str) -> int:
    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/{user_id}").mock(
        return_value=httpx.Response(200, json={"id": user_id})
    )
    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": user_id, "role": role},
        headers=_auth(granter_id),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _owner_member_id(client, org_id: int, user_id: int) -> int:
    members = client.get(f"/api/v1/organizations/{org_id}/members", headers=_auth(user_id)).json()
    return next(m["id"] for m in members if m["user_id"] == user_id)


@respx.mock
def test_admin_cannot_remove_an_owner(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=2, role="admin")
    _add_member(client, org_id, granter_id=1, user_id=3, role="owner")
    target_id = _owner_member_id(client, org_id, 3)

    response = client.delete(
        f"/api/v1/organizations/{org_id}/members/{target_id}", headers=_auth(2)
    )
    assert response.status_code == 403


@respx.mock
def test_admin_cannot_remove_another_admin(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=2, role="admin")
    other_admin_id = _add_member(client, org_id, granter_id=1, user_id=3, role="admin")

    response = client.delete(
        f"/api/v1/organizations/{org_id}/members/{other_admin_id}", headers=_auth(2)
    )
    assert response.status_code == 403


@respx.mock
def test_owner_can_remove_another_owner(client):
    org_id = _make_org(client, owner_id=1)
    second_owner_id = _add_member(client, org_id, granter_id=1, user_id=2, role="owner")

    response = client.delete(
        f"/api/v1/organizations/{org_id}/members/{second_owner_id}", headers=_auth(1)
    )
    assert response.status_code == 204


@respx.mock
def test_cannot_remove_the_last_owner(client):
    org_id = _make_org(client, owner_id=1)
    own_member_id = _owner_member_id(client, org_id, 1)

    response = client.delete(
        f"/api/v1/organizations/{org_id}/members/{own_member_id}", headers=_auth(1)
    )
    assert response.status_code == 422
    assert "last owner" in response.json()["detail"]


@respx.mock
def test_owner_can_remove_plain_member(client):
    org_id = _make_org(client, owner_id=1)
    member_id = _add_member(client, org_id, granter_id=1, user_id=2, role="member")

    response = client.delete(
        f"/api/v1/organizations/{org_id}/members/{member_id}", headers=_auth(1)
    )
    assert response.status_code == 204


@respx.mock
def test_admin_can_remove_plain_member(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=2, role="admin")
    member_id = _add_member(client, org_id, granter_id=1, user_id=3, role="member")

    response = client.delete(
        f"/api/v1/organizations/{org_id}/members/{member_id}", headers=_auth(2)
    )
    assert response.status_code == 204


@respx.mock
def test_member_routes_404_after_org_soft_deleted(client):
    org_id = _make_org(client, owner_id=1)
    assert client.get(f"/api/v1/organizations/{org_id}/members", headers=_auth(1)).status_code == 200

    assert client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(1)).status_code == 204

    listed = client.get(f"/api/v1/organizations/{org_id}/members", headers=_auth(1))
    assert listed.status_code == 404

    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/2").mock(
        return_value=httpx.Response(200, json={"id": 2})
    )
    added = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 2, "role": "member"},
        headers=_auth(1),
    )
    assert added.status_code == 404
