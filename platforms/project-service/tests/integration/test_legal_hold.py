"""Legal hold: while a project is on hold, nothing of it may be deleted by retention. Owners and
admins place and release it, with a reason; the retention list carries it to ingestion."""
import base64

import pytest

from src.project.core.config import settings

PASSWORD = "internal-test-password"


@pytest.fixture
def internal(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_USERNAME", "ingestion-service")
    monkeypatch.setattr(settings, "INTERNAL_API_PASSWORD", PASSWORD)
    token = base64.b64encode(f"ingestion-service:{PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def url(project):
    return f"/api/v1/projects/{project.id}/legal-hold"


def test_an_admin_places_a_hold_with_a_reason_and_it_shows_on_the_project(client, auth, org_role, make_project):
    project = make_project()
    org_role("admin")
    response = client.put(url(project), json={"reason": "Audit 2026-Q4"}, headers=auth(user_id=7))
    assert response.status_code == 200, response.text
    hold = response.json()["legal_hold"]
    assert hold["reason"] == "Audit 2026-Q4" and hold["by"] == 7 and hold["since"]

    body = client.get(f"/api/v1/projects/{project.id}", headers=auth()).json()
    assert body["legal_hold"]["reason"] == "Audit 2026-Q4"


def test_releasing_clears_it(client, auth, org_role, make_project):
    project = make_project()
    org_role("owner")
    client.put(url(project), json={"reason": "Audit"}, headers=auth())
    response = client.delete(url(project), headers=auth())
    assert response.status_code == 200
    assert response.json()["legal_hold"] is None


@pytest.mark.parametrize("role", ["member", "viewer", "billing_manager"])
def test_only_owners_and_admins_change_it(client, auth, org_role, make_project, role):
    project = make_project()
    org_role(role)
    assert client.put(url(project), json={"reason": "x"}, headers=auth()).status_code == 403
    assert client.delete(url(project), headers=auth()).status_code == 403


def test_a_reason_is_required(client, auth, org_role, make_project):
    project = make_project()
    org_role("owner")
    assert client.put(url(project), json={"reason": "   "}, headers=auth()).status_code == 422
    assert client.put(url(project), json={}, headers=auth()).status_code == 422


def test_a_new_project_is_not_on_hold(client, auth, org_role, make_project):
    project = make_project()
    org_role("viewer")
    assert client.get(f"/api/v1/projects/{project.id}", headers=auth()).json()["legal_hold"] is None


def test_the_retention_list_says_which_projects_are_on_hold(client, auth, org_role, make_project, internal):
    held = make_project(name="Held")
    free = make_project(name="Free")
    org_role("owner")
    client.put(url(held), json={"reason": "Litigation"}, headers=auth())

    projects = {p["project_id"]: p for p in client.get("/internal/v1/projects/retention", headers=internal).json()["projects"]}
    assert projects[held.id]["legal_hold"] is True
    assert projects[free.id]["legal_hold"] is False
