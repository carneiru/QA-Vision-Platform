"""POST /collect/token: a project's API key traded for a 5-minute import token (ADR-024)."""
import jwt
import pytest

from src.ingestion.core.config import settings

URL = "/api/v1/collect/token"


def bearer(key):
    return {"Authorization": f"Bearer {key}"}


def test_a_key_is_traded_for_a_short_import_token(client, make_key, db):
    row, key = make_key(project_id=7, organization_id=3)
    response = client.post(URL, headers=bearer(key))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expires_in"] == 300 and body["project_id"] == 7
    claims = jwt.decode(body["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert claims["sub"] == f"apikey:{row.id}"
    assert (claims["project_id"], claims["organization_id"]) == (7, 3)
    assert (claims["scope"], claims["token_type"]) == ("cases:import", "service")
    assert claims["exp"] - claims["iat"] == 300
    db.refresh(row)
    assert row.last_used_at is not None


@pytest.mark.parametrize("headers", [{}, bearer("not-a-key"), bearer("qeos_unknown_key_000000")])
def test_no_valid_key_is_401(client, headers):
    assert client.post(URL, headers=headers).status_code == 401


def test_a_revoked_key_gets_no_token(client, make_key):
    _, key = make_key(revoked=True)
    assert client.post(URL, headers=bearer(key)).status_code == 401


def test_the_import_token_opens_no_ingestion_route(client, make_key):
    _, key = make_key(project_id=7)
    token = client.post(URL, headers=bearer(key)).json()["token"]
    assert client.get("/api/v1/projects/7/runs", headers=bearer(token)).status_code == 401
