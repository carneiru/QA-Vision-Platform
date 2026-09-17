import jwt
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


def test_create_organization_makes_creator_owner(client):
    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme", "slug": "acme", "plan_tier": "free"},
        headers=_auth(7),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme"
    assert body["slug"] == "acme"
    org_id = body["id"]

    get_response = client.get(f"/api/v1/organizations/{org_id}", headers=_auth(7))
    assert get_response.status_code == 200
    assert get_response.json()["id"] == org_id


def test_get_organization_requires_auth(client):
    response = client.get("/api/v1/organizations/1")
    assert response.status_code == 401


def test_get_nonexistent_organization_404(client):
    response = client.get("/api/v1/organizations/999", headers=_auth(7))
    assert response.status_code == 404


def test_update_organization(client):
    create = client.post(
        "/api/v1/organizations",
        json={"name": "Beta", "slug": "beta", "plan_tier": "free"},
        headers=_auth(1),
    )
    org_id = create.json()["id"]

    update = client.patch(
        f"/api/v1/organizations/{org_id}",
        json={"plan_tier": "pro"},
        headers=_auth(1),
    )
    assert update.status_code == 200
    assert update.json()["plan_tier"] == "pro"


def test_create_organization_duplicate_slug_returns_409(client):
    response = client.post(
        "/api/v1/organizations",
        json={"name": "Delta", "slug": "delta", "plan_tier": "free"},
        headers=_auth(3),
    )
    assert response.status_code == 201

    duplicate = client.post(
        "/api/v1/organizations",
        json={"name": "Delta Two", "slug": "delta", "plan_tier": "free"},
        headers=_auth(3),
    )
    assert duplicate.status_code == 409


def test_delete_organization_soft_deletes(client):
    create = client.post(
        "/api/v1/organizations",
        json={"name": "Gamma", "slug": "gamma", "plan_tier": "free"},
        headers=_auth(1),
    )
    org_id = create.json()["id"]

    delete = client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(1))
    assert delete.status_code == 204

    get_after = client.get(f"/api/v1/organizations/{org_id}", headers=_auth(1))
    assert get_after.status_code == 404
