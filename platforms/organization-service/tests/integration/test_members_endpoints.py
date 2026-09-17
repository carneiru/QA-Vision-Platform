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
    return response.json()["id"]


@respx.mock
def test_owner_can_add_member(client):
    org_id = _make_org(client, owner_id=1)
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/2").mock(return_value=httpx.Response(200, json={"id": 2}))

    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 2, "role": "member"},
        headers=_auth(1),
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == 2
    assert response.json()["role"] == "member"


@respx.mock
def test_non_admin_cannot_add_member(client):
    org_id = _make_org(client, owner_id=1)
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/3").mock(return_value=httpx.Response(200, json={"id": 3}))
    client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 3, "role": "member"},
        headers=_auth(1),
    )

    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/4").mock(return_value=httpx.Response(200, json={"id": 4}))
    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 4, "role": "member"},
        headers=_auth(3),  # user 3 is a plain member, not owner/admin
    )
    assert response.status_code == 403


@respx.mock
def test_add_nonexistent_user_returns_422(client):
    org_id = _make_org(client, owner_id=1)
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/999").mock(return_value=httpx.Response(404))

    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 999, "role": "member"},
        headers=_auth(1),
    )
    assert response.status_code == 422


@respx.mock
def test_list_members(client):
    org_id = _make_org(client, owner_id=1)
    response = client.get(f"/api/v1/organizations/{org_id}/members", headers=_auth(1))
    assert response.status_code == 200
    members = response.json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"


@respx.mock
def test_owner_can_remove_member(client):
    org_id = _make_org(client, owner_id=1)
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/2").mock(return_value=httpx.Response(200, json={"id": 2}))
    add_response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 2, "role": "member"},
        headers=_auth(1),
    )
    member_id = add_response.json()["id"]

    response = client.delete(f"/api/v1/organizations/{org_id}/members/{member_id}", headers=_auth(1))
    assert response.status_code == 204


@respx.mock
def test_admin_can_add_member_with_member_role(client):
    org_id = _make_org(client, owner_id=1)

    # Add user 2 as admin
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/2").mock(return_value=httpx.Response(200, json={"id": 2}))
    admin_response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 2, "role": "admin"},
        headers=_auth(1),
    )
    assert admin_response.status_code == 201

    # Admin (user 2) should be able to add user 3 with role "member"
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/3").mock(return_value=httpx.Response(200, json={"id": 3}))
    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 3, "role": "member"},
        headers=_auth(2),
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == 3
    assert response.json()["role"] == "member"


@respx.mock
def test_admin_cannot_add_member_with_admin_role(client):
    org_id = _make_org(client, owner_id=1)

    # Add user 2 as admin
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/2").mock(return_value=httpx.Response(200, json={"id": 2}))
    admin_response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 2, "role": "admin"},
        headers=_auth(1),
    )
    assert admin_response.status_code == 201

    # Admin (user 2) should NOT be able to add user 3 with role "admin"
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/3").mock(return_value=httpx.Response(200, json={"id": 3}))
    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 3, "role": "admin"},
        headers=_auth(2),
    )
    assert response.status_code == 403


@respx.mock
def test_admin_cannot_add_member_with_owner_role(client):
    org_id = _make_org(client, owner_id=1)

    # Add user 2 as admin
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/2").mock(return_value=httpx.Response(200, json={"id": 2}))
    admin_response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 2, "role": "admin"},
        headers=_auth(1),
    )
    assert admin_response.status_code == 201

    # Admin (user 2) should NOT be able to add user 3 with role "owner"
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/3").mock(return_value=httpx.Response(200, json={"id": 3}))
    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 3, "role": "owner"},
        headers=_auth(2),
    )
    assert response.status_code == 403


@respx.mock
def test_owner_can_add_member_with_admin_role(client):
    org_id = _make_org(client, owner_id=1)

    # Owner (user 1) should be able to add user 2 with role "admin"
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/2").mock(return_value=httpx.Response(200, json={"id": 2}))
    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 2, "role": "admin"},
        headers=_auth(1),
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == 2
    assert response.json()["role"] == "admin"


@respx.mock
def test_owner_can_add_member_with_owner_role(client):
    org_id = _make_org(client, owner_id=1)

    # Owner (user 1) should be able to add user 2 with role "owner"
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/2").mock(return_value=httpx.Response(200, json={"id": 2}))
    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 2, "role": "owner"},
        headers=_auth(1),
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == 2
    assert response.json()["role"] == "owner"
