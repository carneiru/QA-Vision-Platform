import pytest

from src.ingestion.models import ApiKey
from src.ingestion.utils.keys import hash_key

ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")
EDITORS = ("owner", "admin", "member")
BASE = "/api/v1/projects/1/api-keys"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_create_is_for_editors(client, auth, project_role, role):
    project_role(role)
    response = client.post(BASE, json={"name": "GitHub Actions"}, headers=auth())
    assert response.status_code == (201 if role in EDITORS else 403)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_list_is_for_every_role(client, auth, project_role, role):
    project_role(role)
    assert client.get(BASE, headers=auth()).status_code == 200


@pytest.mark.parametrize("role", ALL_ROLES)
def test_revoke_is_for_editors(client, auth, project_role, make_key, role):
    row, _ = make_key()
    project_role(role)
    response = client.delete(f"{BASE}/{row.id}", headers=auth())
    assert response.status_code == (204 if role in EDITORS else 403)


def test_create_returns_the_key_once_and_stores_only_its_hash(client, auth, project_role, db):
    project_role("admin", organization_id=77)
    body = client.post(BASE, json={"name": "GitHub Actions"}, headers=auth(9)).json()
    assert body["key"].startswith("qav_")
    assert body["key_prefix"] == body["key"][:12]
    row = db.query(ApiKey).one()
    assert row.key_hash == hash_key(body["key"])
    assert body["key"] not in {row.key_hash, row.key_prefix, row.name}
    assert (row.project_id, row.organization_id, row.created_by) == (1, 77, 9)

    listed = client.get(BASE, headers=auth()).json()
    assert listed[0]["key_prefix"] == body["key_prefix"]
    assert "key" not in listed[0] and "key_hash" not in listed[0]


@pytest.mark.parametrize("name", ["", "   ", "x" * 256])
def test_invalid_name_is_422(client, auth, project_role, name):
    project_role("owner")
    assert client.post(BASE, json={"name": name}, headers=auth()).status_code == 422


def test_unknown_field_is_422(client, auth, project_role):
    project_role("owner")
    assert client.post(BASE, json={"name": "k", "scopes": ["all"]}, headers=auth()).status_code == 422


def test_list_shows_only_this_projects_keys(client, auth, project_role, make_key):
    make_key(project_id=1, name="mine")
    make_key(project_id=2, name="theirs")
    project_role("viewer")
    assert [k["name"] for k in client.get(BASE, headers=auth()).json()] == ["mine"]


def test_revoke_sets_revoked_at_and_is_repeatable(client, auth, project_role, make_key, db):
    row, _ = make_key()
    project_role("member")
    assert client.delete(f"{BASE}/{row.id}", headers=auth()).status_code == 204
    db.refresh(row)
    first = row.revoked_at
    assert first is not None
    assert client.delete(f"{BASE}/{row.id}", headers=auth()).status_code == 204
    db.refresh(row)
    assert row.revoked_at == first


def test_revoking_another_projects_key_is_404(client, auth, project_role, make_key, db):
    row, _ = make_key(project_id=2)
    project_role("owner", project_id=1)
    assert client.delete(f"{BASE}/{row.id}", headers=auth()).status_code == 404
    db.refresh(row)
    assert row.revoked_at is None


def test_non_member_is_404(client, auth, project_role):
    project_role(status_code=404, body={"detail": "Project not found"})
    assert client.get(BASE, headers=auth()).status_code == 404
