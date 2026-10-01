import base64
from datetime import datetime, timezone

import pytest

from src.project.core.config import settings

URL = "/internal/v1/projects/retention"
PASSWORD = "internal-test-password"


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_USERNAME", "ingestion-service")
    monkeypatch.setattr(settings, "INTERNAL_API_PASSWORD", PASSWORD)


def basic(user, password):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


def test_correct_credentials_list_every_project_with_its_retention(client, configured, make_project, db):
    default = make_project(name="Default")
    custom = make_project(name="Custom")
    custom.settings = {"result_retention_days": 30}
    gone = make_project(name="Gone")
    gone.deleted_at = datetime.now(timezone.utc)
    db.commit()

    response = client.get(URL, headers=basic("ingestion-service", PASSWORD))

    assert response.status_code == 200
    assert response.json() == {"projects": [
        {"project_id": default.id, "result_retention_days": 90, "deleted": False},
        {"project_id": custom.id, "result_retention_days": 30, "deleted": False},
        {"project_id": gone.id, "result_retention_days": 90, "deleted": True},
    ]}


@pytest.mark.parametrize("headers", [
    {},
    basic("ingestion-service", "wrong"),
    basic("someone-else", PASSWORD),
    {"Authorization": "Bearer not-basic"},
])
def test_missing_or_wrong_credentials_are_401(client, configured, headers):
    response = client.get(URL, headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Basic"


def test_a_user_token_is_not_accepted(client, configured, auth):
    assert client.get(URL, headers=auth()).status_code == 401


def test_without_a_password_the_endpoint_is_off(client, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_PASSWORD", "")
    response = client.get(URL, headers=basic("ingestion-service", ""))
    assert response.status_code == 503
    assert response.json() == {"detail": "Internal API is not configured"}


def test_internal_credentials_do_not_open_the_public_api(client, configured, make_project):
    project = make_project()
    assert client.get(f"/api/v1/projects/{project.id}", headers=basic("ingestion-service", PASSWORD)).status_code == 401


def test_the_endpoint_is_not_in_the_public_openapi(client):
    assert "/internal/v1/projects/retention" not in client.get("/api/v1/openapi.json").json()["paths"]
