import jwt
from datetime import datetime, timedelta, timezone
from src.organization.core.config import settings
from src.organization.models.member import OrganizationMember


def _token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _auth(user_id: int) -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _create(client, user_id: int, name: str, slug: str) -> int:
    r = client.post(
        "/api/v1/organizations",
        json={"name": name, "slug": slug, "plan_tier": "free"},
        headers=_auth(user_id),
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_list_requires_auth(client):
    assert client.get("/api/v1/organizations").status_code == 401


def test_list_returns_only_my_orgs_with_role(client):
    mine = _create(client, 7, "Mine", "mine")
    _create(client, 8, "Theirs", "theirs")

    r = client.get("/api/v1/organizations", headers=_auth(7))
    assert r.status_code == 200
    body = r.json()
    assert [o["id"] for o in body] == [mine]
    assert body[0]["role"] == "owner"
    assert body[0]["name"] == "Mine"


def test_list_empty_for_user_with_no_orgs(client):
    r = client.get("/api/v1/organizations", headers=_auth(99))
    assert r.status_code == 200
    assert r.json() == []


def test_list_excludes_soft_deleted(client):
    org_id = _create(client, 7, "Gone", "gone")
    assert client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(7)).status_code == 204
    r = client.get("/api/v1/organizations", headers=_auth(7))
    assert [o["id"] for o in r.json()] == []


def test_list_excludes_inactive_membership(client, db):
    org_id = _create(client, 7, "Acme", "acme")
    member = (
        db.query(OrganizationMember)
        .filter_by(organization_id=org_id, user_id=7)
        .one()
    )
    member.status = "suspended"
    db.commit()
    r = client.get("/api/v1/organizations", headers=_auth(7))
    assert r.json() == []


def test_list_ordered_by_name(client):
    _create(client, 7, "Zeta", "zeta")
    _create(client, 7, "Alpha", "alpha")
    r = client.get("/api/v1/organizations", headers=_auth(7))
    assert [o["name"] for o in r.json()] == ["Alpha", "Zeta"]
