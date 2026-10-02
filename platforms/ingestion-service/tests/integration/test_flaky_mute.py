"""Muting a flaky test acknowledges it: it leaves the default flaky list but
stays retrievable with include_muted=true, and can be unmuted."""

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.models import Run, RunResult
from src.ingestion.service.ingest_service import test_key as key_of

BASE = "/api/v1/projects/1/analytics"


@pytest.fixture
def seed(db, make_key):
    keys = {}

    def _seed(project_id=1, minutes_ago=0, results=(("t1", "passed", 10),)):
        if project_id not in keys:
            keys[project_id] = make_key(project_id=project_id)[0]
        start = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        counts = Counter(status for _, status, _ in results)
        run = Run(project_id=project_id, api_key_id=keys[project_id].id, request_hash="h",
                  ci_provider="local", branch="main", started_at=start,
                  finished_at=start + timedelta(seconds=1), duration_ms=1000, total=len(results),
                  passed=counts["passed"], failed=counts["failed"], skipped=counts["skipped"],
                  errored=counts["errored"], created_at=start)
        db.add(run)
        db.flush()
        for name, status, duration in results:
            db.add(RunResult(run_id=run.id, test_key=key_of("s", "C", name), suite="s",
                             class_name="C", name=name, status=status, duration_ms=duration,
                             message=None))
        db.commit()
        return run

    return _seed


def _flip_seed(seed, name="flipper"):
    for i, status in enumerate(("passed", "failed", "passed", "failed", "passed")):
        seed(minutes_ago=50 - i, results=((name, status, 1),))


def _flaky_keys(client, auth, query=""):
    response = client.get(f"{BASE}/flaky{query}", headers=auth())
    assert response.status_code == 200, response.text
    return response.json()


def _mute(client, auth, test_key):
    return client.put(f"{BASE}/flaky/mute", json={"test_key": test_key}, headers=auth())


def test_mute_removes_from_default_list_and_include_muted_shows_it(client, auth, project_role, seed):
    project_role()
    _flip_seed(seed)
    items = _flaky_keys(client, auth)
    assert len(items) == 1
    key = items[0]["test_key"]

    assert _mute(client, auth, key).status_code == 204
    assert _flaky_keys(client, auth) == []

    with_muted = _flaky_keys(client, auth, "?include_muted=true")
    assert [(i["test_key"], i["muted"]) for i in with_muted] == [(key, True)]


def test_unmuted_rows_carry_muted_false(client, auth, project_role, seed):
    project_role()
    _flip_seed(seed)
    items = _flaky_keys(client, auth, "?include_muted=true")
    assert items[0]["muted"] is False


def test_mute_is_idempotent_and_unmute_restores(client, auth, project_role, seed):
    project_role()
    _flip_seed(seed)
    key = _flaky_keys(client, auth)[0]["test_key"]

    assert _mute(client, auth, key).status_code == 204
    assert _mute(client, auth, key).status_code == 204  # second mute is a no-op

    response = client.delete(f"{BASE}/flaky/mute/{key}", headers=auth())
    assert response.status_code == 204
    assert [i["test_key"] for i in _flaky_keys(client, auth)] == [key]


def test_unmuting_a_test_that_is_not_muted_is_404(client, auth, project_role):
    project_role()
    response = client.delete(f"{BASE}/flaky/mute/{'0' * 64}", headers=auth())
    assert response.status_code == 404


@pytest.mark.parametrize("role", ("viewer", "billing_manager"))
def test_reading_roles_cannot_mute(client, auth, project_role, role, seed):
    project_role(role)
    _flip_seed(seed)
    key = _flaky_keys(client, auth)[0]["test_key"]
    assert _mute(client, auth, key).status_code == 403


def test_mutes_are_scoped_to_the_project(client, auth, project_role, seed, db):
    project_role()
    _flip_seed(seed)
    key = _flaky_keys(client, auth)[0]["test_key"]
    assert _mute(client, auth, key).status_code == 204

    # The same test_key in another project is untouched.
    from src.ingestion.models.muted import MutedTest

    rows = db.query(MutedTest).all()
    assert [(r.project_id, r.test_key) for r in rows] == [(1, key)]
