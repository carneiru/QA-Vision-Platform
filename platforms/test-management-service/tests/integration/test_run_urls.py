"""GET /run-requests/run-urls: the GitHub run URLs of Play requests, for the report's origin filter."""
from datetime import datetime, timedelta, timezone

import pytest

from src.casebook.models import RunRequest
from src.casebook.service import run_request_service

P = "/api/v1/projects/1/run-requests"
NOW = datetime.now(timezone.utc)


def add(db, days_ago, url, project_id=1, status="completed"):
    db.add(RunRequest(project_id=project_id, requested_by=1, requested_at=NOW - timedelta(days=days_ago),
                      selection=[], status=status, github_run_url=url))


@pytest.fixture
def seeded(db, project_role):
    project_role("viewer")
    add(db, 1, "https://github.com/acme/obt/actions/runs/3")
    add(db, 5, "https://github.com/acme/obt/actions/runs/2")
    add(db, 6, None, status="failed_to_start")
    add(db, 40, "https://github.com/acme/obt/actions/runs/1")
    add(db, 2, "https://github.com/other/repo/actions/runs/9", project_id=2)
    db.commit()


def since(days):
    return (NOW - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_urls_since_newest_first_without_nulls(client, auth, seeded):
    body = client.get(f"{P}/run-urls", params={"since": since(10)}, headers=auth()).json()
    assert body == {"urls": ["https://github.com/acme/obt/actions/runs/3", "https://github.com/acme/obt/actions/runs/2"],
                    "truncated": False}


def test_the_route_is_not_taken_for_a_request_id(client, auth, seeded):
    assert client.get(f"{P}/run-urls", params={"since": since(60)}, headers=auth()).status_code == 200


def test_since_is_required_and_at_most_500_days_back(client, auth, seeded):
    assert client.get(f"{P}/run-urls", headers=auth()).status_code == 422
    assert client.get(f"{P}/run-urls", params={"since": since(501)}, headers=auth()).status_code == 422
    assert client.get(f"{P}/run-urls", params={"since": since(499)}, headers=auth()).status_code == 200
    assert client.get(f"{P}/run-urls", params={"since": "yesterday"}, headers=auth()).status_code == 422


def test_truncated_above_the_cap(client, auth, seeded, monkeypatch):
    monkeypatch.setattr(run_request_service, "MAX_RUN_URLS", 2)
    body = client.get(f"{P}/run-urls", params={"since": since(60)}, headers=auth()).json()
    assert len(body["urls"]) == 2 and body["truncated"] is True


def test_roles(client, auth, seeded, project_role):
    for role in ("owner", "admin", "member", "viewer", "billing_manager"):
        project_role(role)
        assert client.get(f"{P}/run-urls", params={"since": since(10)}, headers=auth()).status_code == 200
    project_role(status_code=404, body={"detail": "Project not found"})
    assert client.get(f"{P}/run-urls", params={"since": since(10)}, headers=auth()).status_code == 404
