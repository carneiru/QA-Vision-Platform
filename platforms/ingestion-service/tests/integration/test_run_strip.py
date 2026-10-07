"""POST /analytics/run-strip: each test's status in the project's last N runs (Cases 'Last runs')."""
from datetime import datetime, timedelta, timezone

import pytest

from qeos_shared.keys import test_key

URL = "/api/v1/projects/7/analytics/run-strip"
A, B, C = (test_key("", "", n) for n in "ABC")


def upload(client, key, *, started, results, branch="main"):
    run = {"ci_provider": "local", "branch": branch, "started_at": started.isoformat(),
           "finished_at": (started + timedelta(minutes=1)).isoformat()}
    r = client.post("/api/v1/collect/runs", json={"run": run, "results": results},
                    headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 201, r.text


@pytest.fixture
def runs(client, make_key, project_role):
    project_role("viewer", project_id=7)
    _, key = make_key(project_id=7)
    now = datetime.now(timezone.utc)
    upload(client, key, started=now - timedelta(hours=4), results=[{"name": "A", "status": "passed"}])
    upload(client, key, started=now - timedelta(hours=3), results=[
        {"name": "A", "status": "failed"}, {"name": "A", "status": "passed"}, {"name": "B", "status": "errored"}])
    upload(client, key, started=now - timedelta(hours=2), branch="dev", results=[{"name": "A", "status": "skipped"}])
    upload(client, key, started=now - timedelta(hours=1), results=[{"name": "B", "status": "passed"}])
    return client


def strip(client, auth, **body):
    r = client.post(URL, json={"test_keys": [A, B, C], **body}, headers=auth())
    assert r.status_code == 200, r.text
    return r.json()


def test_runs_are_oldest_to_newest_and_aligned_for_every_key(runs, auth):
    data = strip(runs, auth)
    assert len(data["runs"]) == 4
    assert [r["started_at"] for r in data["runs"]] == sorted(r["started_at"] for r in data["runs"])
    assert data["statuses"][A] == ["passed", "rerun", "skipped", None]
    assert data["statuses"][B] == [None, "failed", None, "passed"]   # errored counts as failed
    assert data["statuses"][C] == [None, None, None, None]


def test_a_retried_test_is_a_rerun_whatever_the_outcome(runs, auth):
    assert strip(runs, auth)["statuses"][A][1] == "rerun"


def test_limit_keeps_the_newest_runs(runs, auth):
    data = strip(runs, auth, limit=2)
    assert data["statuses"][A] == ["skipped", None]


def test_branch_only_counts_that_branchs_runs(runs, auth):
    data = strip(runs, auth, branch="main")
    assert len(data["runs"]) == 3 and data["statuses"][A] == ["passed", "rerun", None]


def test_keys_are_case_insensitive(runs, auth):
    r = runs.post(URL, json={"test_keys": [A.upper()]}, headers=auth())
    assert r.json()["statuses"][A] == ["passed", "rerun", "skipped", None]


def test_other_projects_runs_are_invisible(runs, auth, make_key, project_role):
    project_role("viewer", project_id=8)
    _, other = make_key(project_id=8)
    upload(runs, other, started=datetime.now(timezone.utc), results=[{"name": "A", "status": "failed"}])
    assert len(strip(runs, auth)["runs"]) == 4


@pytest.mark.parametrize("body", [{"test_keys": []}, {"test_keys": ["x"]}, {"test_keys": [A] * 201},
                                  {"test_keys": [A], "limit": 21}, {"test_keys": [A], "branch": "a\x00"}])
def test_bad_bodies_are_422(runs, auth, body):
    assert runs.post(URL, json=body, headers=auth()).status_code == 422


def test_runs_with_identical_started_at_are_ordered_by_id(client, make_key, project_role, auth):
    project_role("viewer", project_id=7)
    _, key = make_key(project_id=7)
    same = datetime.now(timezone.utc) - timedelta(hours=1)
    upload(client, key, started=same, results=[{"name": "A", "status": "passed"}])
    upload(client, key, started=same, results=[{"name": "A", "status": "failed"}])
    data = strip(client, auth)
    assert [r["id"] for r in data["runs"]] == sorted(r["id"] for r in data["runs"])
    assert len(data["runs"]) == 2
    assert data["statuses"][A] == ["passed", "failed"]


def test_duplicate_and_mixed_case_keys_map_to_one_lowercased_entry(runs, auth):
    r = runs.post(URL, json={"test_keys": [A, A.upper(), A.title()]}, headers=auth())
    assert r.status_code == 200, r.text
    assert list(r.json()["statuses"]) == [A]


def test_unknown_body_fields_are_422(runs, auth):
    assert runs.post(URL, json={"test_keys": [A], "extra": 1}, headers=auth()).status_code == 422
