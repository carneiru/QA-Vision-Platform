"""The members/me contract project-service depends on.

docs/superpowers/specs/2026-09-28-project-service-design.md pins this response shape; project-service
treats any other 200 body as "organization service unavailable". Do not add keys without changing both.
"""
import jwt
import pytest
from datetime import datetime, timedelta, timezone
from src.organization.core.config import settings
from src.organization.models.member import OrganizationMember


def _auth(user_id: int) -> dict:
    token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def _make_org(client, owner_id: int = 1) -> int:
    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme", "slug": "acme", "plan_tier": "free"},
        headers=_auth(owner_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _add_member(db, org_id: int, user_id: int, role: str, status: str = "active") -> None:
    db.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, status=status))
    db.commit()


@pytest.mark.parametrize("role", OrganizationMember.ROLES)
def test_active_member_gets_exactly_their_role(client, db, role):
    org_id = _make_org(client, owner_id=1)
    if role != "owner":
        _add_member(db, org_id, user_id=2, role=role)
    caller = 1 if role == "owner" else 2

    response = client.get(f"/api/v1/organizations/{org_id}/members/me", headers=_auth(caller))

    assert response.status_code == 200
    assert response.json() == {"role": role}


def test_non_member_gets_404(client):
    org_id = _make_org(client, owner_id=1)
    response = client.get(f"/api/v1/organizations/{org_id}/members/me", headers=_auth(99))
    assert response.status_code == 404


def test_suspended_member_gets_404(client, db):
    org_id = _make_org(client, owner_id=1)
    _add_member(db, org_id, user_id=2, role="admin", status="suspended")
    response = client.get(f"/api/v1/organizations/{org_id}/members/me", headers=_auth(2))
    assert response.status_code == 404


def test_deleted_organization_gets_404_even_for_owner(client):
    org_id = _make_org(client, owner_id=1)
    assert client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(1)).status_code == 204
    response = client.get(f"/api/v1/organizations/{org_id}/members/me", headers=_auth(1))
    assert response.status_code == 404


def test_missing_token_gets_401(client):
    org_id = _make_org(client, owner_id=1)
    response = client.get(f"/api/v1/organizations/{org_id}/members/me")
    assert response.status_code == 401
