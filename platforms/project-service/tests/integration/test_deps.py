import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from conftest import make_token
from src.project.api.deps import (
    EDIT_ROLES, MANAGE_ROLES, OrgAccess, ProjectAccess, get_db, require_org_role, require_project_role,
)

probe_app = FastAPI()


@probe_app.get("/orgs/{org_id}/probe")
def org_probe(access: OrgAccess = Depends(require_org_role(*MANAGE_ROLES))):
    return {"org_id": access.org_id, "user_id": access.user_id, "role": access.role}


@probe_app.get("/projects/{project_id}/probe")
def project_probe(access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES))):
    return {"project_id": access.project.id, "user_id": access.user_id, "role": access.role}


@pytest.fixture
def probe(db):
    probe_app.dependency_overrides[get_db] = lambda: db
    with TestClient(probe_app) as c:
        yield c
    probe_app.dependency_overrides.clear()


def test_missing_token_is_401_without_calling_org_service(probe, http):
    assert probe.get("/orgs/1/probe").status_code == 401
    assert not http.calls


def test_refresh_token_is_401(probe):
    headers = {"Authorization": f"Bearer {make_token(1, token_type='refresh')}"}
    assert probe.get("/orgs/1/probe", headers=headers).status_code == 401


def test_allowed_org_role_passes_through(probe, auth, org_role):
    org_role("admin", org_id=1)
    response = probe.get("/orgs/1/probe", headers=auth(5))
    assert response.status_code == 200
    assert response.json() == {"org_id": 1, "user_id": 5, "role": "admin"}


def test_insufficient_org_role_is_403(probe, auth, org_role):
    org_role("member", org_id=1)
    assert probe.get("/orgs/1/probe", headers=auth()).status_code == 403


def test_non_member_of_org_is_404(probe, auth, org_role):
    org_role(org_id=1, status_code=404, body={"detail": "Not a member"})
    response = probe.get("/orgs/1/probe", headers=auth())
    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found"


def test_org_service_401_is_401(probe, auth, org_role):
    org_role(org_id=1, status_code=401, body={"detail": "bad"})
    assert probe.get("/orgs/1/probe", headers=auth()).status_code == 401


def test_org_service_down_is_503(probe, auth, org_role):
    org_role(org_id=1, exc=httpx.ConnectError("refused"))
    response = probe.get("/orgs/1/probe", headers=auth())
    assert response.status_code == 503
    assert response.json()["detail"] == "Organization service unavailable"


def test_project_role_is_checked_against_the_projects_own_org(probe, auth, org_role, make_project):
    project = make_project(org_id=42)
    route = org_role("member", org_id=42)
    response = probe.get(f"/projects/{project.id}/probe", headers=auth(3))
    assert response.status_code == 200
    assert response.json() == {"project_id": project.id, "user_id": 3, "role": "member"}
    assert route.called


def test_member_of_another_org_cannot_reach_the_project(probe, auth, org_role, make_project):
    project = make_project(org_id=42)
    org_role("owner", org_id=1)                                            # caller owns org 1 ...
    org_role(org_id=42, status_code=404, body={"detail": "Not a member"})  # ... but not org 42
    response = probe.get(f"/projects/{project.id}/probe", headers=auth())
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_missing_project_is_404_without_calling_org_service(probe, auth, http):
    assert probe.get("/projects/999/probe", headers=auth()).status_code == 404
    assert not http.calls


def test_soft_deleted_project_is_404_even_for_owner(probe, auth, org_role, make_project, db):
    from datetime import datetime, timezone

    project = make_project()
    project.deleted_at = datetime.now(timezone.utc)
    db.commit()
    org_role("owner")
    assert probe.get(f"/projects/{project.id}/probe", headers=auth()).status_code == 404


def test_insufficient_project_role_is_403(probe, auth, org_role, make_project):
    project = make_project()
    org_role("viewer")
    assert probe.get(f"/projects/{project.id}/probe", headers=auth()).status_code == 403


@pytest.mark.parametrize("claims", [{"purpose": "mfa"}, {"token_type": "service"}, {"purpose": "password_reset"}])
def test_non_access_tokens_are_401(probe, http, claims):
    headers = {"Authorization": f"Bearer {make_token(5, **claims)}"}
    assert probe.get("/orgs/1/probe", headers=headers).status_code == 401
    assert probe.get("/projects/1/probe", headers=headers).status_code == 401
    assert not http.calls
