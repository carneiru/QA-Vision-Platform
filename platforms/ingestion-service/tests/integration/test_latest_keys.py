"""GET /analytics/latest-keys: tests whose most recent result has a status (case filters)."""
from datetime import datetime, timedelta, timezone

import pytest

from qav_shared.keys import test_key

URL = "/api/v1/projects/7/analytics/latest-keys"


def upload(client, key, *, branch, started, results):
    run = {"ci_provider": "local", "branch": branch, "started_at": started.isoformat(),
           "finished_at": (started + timedelta(minutes=1)).isoformat()}
    r = client.post("/api/v1/collect/runs", json={"run": run, "results": results},
                    headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 201, r.text


@pytest.fixture
def history(client, make_key, project_role):
    project_role("viewer", project_id=7)
    _, key = make_key(project_id=7)
    now = datetime.now(timezone.utc)
    upload(client, key, branch="main", started=now - timedelta(hours=3), results=[
        {"name": "A", "status": "failed"}, {"name": "B", "status": "failed"}, {"name": "D", "status": "passed"}])
    upload(client, key, branch="main", started=now - timedelta(hours=2), results=[
        {"name": "A", "status": "passed"}, {"name": "C", "status": "skipped"}, {"name": "E", "status": "errored"}])
    upload(client, key, branch="dev", started=now - timedelta(hours=1), results=[{"name": "D", "status": "failed"}])
    return client


def keys(client, auth, query):
    r = client.get(f"{URL}?{query}", headers=auth())
    assert r.status_code == 200, r.text
    return sorted(r.json()["keys"])


def k(*names):
    return sorted(test_key("", "", n) for n in names)


def test_only_the_latest_result_counts(history, auth):
    assert keys(history, auth, "status=passed") == k("A")
    assert keys(history, auth, "status=failed") == k("B", "D", "E")   # errored counts as failed


def test_skipped_and_any(history, auth):
    assert keys(history, auth, "status=skipped") == k("C")
    assert keys(history, auth, "status=any") == k("A", "B", "C", "D", "E")


def test_branch_limits_the_runs(history, auth):
    assert keys(history, auth, "status=passed&branch=main") == k("A", "D")
    assert keys(history, auth, "status=failed&branch=dev") == k("D")


def test_a_bad_status_is_422(history, auth):
    assert history.get(f"{URL}?status=broken", headers=auth()).status_code == 422
