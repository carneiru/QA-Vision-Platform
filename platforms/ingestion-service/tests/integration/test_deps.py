import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from conftest import make_token
from src.ingestion.api.deps import (
    EDIT_ROLES, Caller, ProjectAccess, check_project_role, get_caller, get_db, require_project_role,
)

probe_app = FastAPI()


@probe_app.get("/projects/{project_id}/probe")
def probe(access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES))):
    return access._asdict()


@probe_app.get("/things/{project_id}")
def thing(project_id: int, caller: Caller = Depends(get_caller)):
    return check_project_role(project_id, caller, EDIT_ROLES, "Thing not found")._asdict()


@pytest.fixture
def probe_client(db):
    probe_app.dependency_overrides[get_db] = lambda: db
    with TestClient(probe_app) as c:
        yield c
    probe_app.dependency_overrides.clear()


def test_missing_token_is_401_without_calling_project_service(probe_client, http):
    assert probe_client.get("/projects/1/probe").status_code == 401
    assert not http.calls


def test_refresh_token_is_401(probe_client):
    headers = {"Authorization": f"Bearer {make_token(1, token_type='refresh')}"}
    assert probe_client.get("/projects/1/probe", headers=headers).status_code == 401


def test_allowed_role_passes_with_organization(probe_client, auth, project_role):
    project_role("member", project_id=1, organization_id=10)
    response = probe_client.get("/projects/1/probe", headers=auth(5))
    assert response.status_code == 200
    assert response.json() == {"project_id": 1, "organization_id": 10, "user_id": 5, "role": "member"}


def test_insufficient_role_is_403(probe_client, auth, project_role):
    project_role("viewer")
    assert probe_client.get("/projects/1/probe", headers=auth()).status_code == 403


def test_non_member_is_404(probe_client, auth, project_role):
    project_role(status_code=404, body={"detail": "Project not found"})
    response = probe_client.get("/projects/1/probe", headers=auth())
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_custom_not_found_detail(probe_client, auth, project_role):
    project_role(project_id=3, status_code=404, body={"detail": "Project not found"})
    response = probe_client.get("/things/3", headers=auth())
    assert response.status_code == 404
    assert response.json()["detail"] == "Thing not found"


def test_project_service_401_is_401(probe_client, auth, project_role):
    project_role(status_code=401, body={"detail": "bad"})
    assert probe_client.get("/projects/1/probe", headers=auth()).status_code == 401


def test_project_service_down_is_503(probe_client, auth, project_role):
    project_role(exc=httpx.ConnectError("refused"))
    response = probe_client.get("/projects/1/probe", headers=auth())
    assert response.status_code == 503
    assert response.json()["detail"] == "Project service unavailable"


@pytest.mark.parametrize("claims", [{"purpose": "mfa"}, {"token_type": "service"}, {"purpose": "password_reset"}])
def test_non_access_tokens_are_401(probe_client, http, claims):
    headers = {"Authorization": f"Bearer {make_token(5, **claims)}"}
    assert probe_client.get("/projects/1/probe", headers=headers).status_code == 401
    assert probe_client.get("/things/1", headers=headers).status_code == 401
    assert not http.calls
