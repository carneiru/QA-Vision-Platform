"""Authorization on the organization CRUD routes (previously authenticated-only)."""
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


def _make_org(client, owner_id: int, name="Acme", slug="acme") -> int:
    response = client.post(
        "/api/v1/organizations",
        json={"name": name, "slug": slug, "plan_tier": "free"},
        headers=_auth(owner_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _add_member(client, org_id: int, granter_id: int, user_id: int, role: str) -> int:
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/{user_id}").mock(
        return_value=httpx.Response(200, json={"id": user_id})
    )
    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": user_id, "role": role},
        headers=_auth(granter_id),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_non_member_cannot_read_organization(client):
    org_id = _make_org(client, owner_id=1)
    response = client.get(f"/api/v1/organizations/{org_id}", headers=_auth(99))
    assert response.status_code == 404


def test_non_member_cannot_update_organization(client):
    org_id = _make_org(client, owner_id=1)
    response = client.patch(
        f"/api/v1/organizations/{org_id}", json={"name": "Hijacked"}, headers=_auth(99)
    )
    assert response.status_code == 404


def test_non_member_cannot_delete_organization(client):
    org_id = _make_org(client, owner_id=1)
    response = client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(99))
    assert response.status_code == 404


@respx.mock
def test_plain_member_can_read_but_not_update(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=2, role="member")

    assert client.get(f"/api/v1/organizations/{org_id}", headers=_auth(2)).status_code == 200

    update = client.patch(
        f"/api/v1/organizations/{org_id}", json={"name": "Renamed"}, headers=_auth(2)
    )
    assert update.status_code == 403


@respx.mock
def test_admin_can_update_but_not_delete(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=2, role="admin")

    update = client.patch(
        f"/api/v1/organizations/{org_id}", json={"name": "Renamed"}, headers=_auth(2)
    )
    assert update.status_code == 200

    delete = client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(2))
    assert delete.status_code == 403


def test_owner_can_delete_organization(client):
    org_id = _make_org(client, owner_id=1)
    assert client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(1)).status_code == 204


def test_patch_duplicate_name_returns_409(client):
    _make_org(client, owner_id=1, name="First", slug="first")
    second_id = _make_org(client, owner_id=1, name="Second", slug="second")

    response = client.patch(
        f"/api/v1/organizations/{second_id}", json={"name": "First"}, headers=_auth(1)
    )
    assert response.status_code == 409


def test_create_with_invalid_plan_tier_returns_422(client):
    response = client.post(
        "/api/v1/organizations",
        json={"name": "Bogus", "slug": "bogus", "plan_tier": "platinum"},
        headers=_auth(1),
    )
    assert response.status_code == 422


def test_update_with_invalid_plan_tier_returns_422(client):
    org_id = _make_org(client, owner_id=1)
    response = client.patch(
        f"/api/v1/organizations/{org_id}", json={"plan_tier": "platinum"}, headers=_auth(1)
    )
    assert response.status_code == 422


def test_create_with_valid_plan_tier_accepted(client):
    org_id = _make_org(client, owner_id=1)
    response = client.patch(
        f"/api/v1/organizations/{org_id}", json={"plan_tier": "enterprise_plus"}, headers=_auth(1)
    )
    assert response.status_code == 200
    assert response.json()["plan_tier"] == "enterprise_plus"
