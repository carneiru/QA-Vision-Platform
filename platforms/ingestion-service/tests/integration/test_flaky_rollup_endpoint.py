"""/flaky serves 90-day windows from the rollups; before the rollup job has
run it falls back to the live scan with identical results."""

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.analytics.rollup import upsert_day
from src.ingestion.models import Run, RunResult
from src.ingestion.service.ingest_service import test_key as key_of

BASE = "/api/v1/projects/1/analytics"


@pytest.fixture
def seed(db, make_key):
    keys = {}

    def _seed(project_id=1, days_ago=0, minutes_ago=0, results=(("t1", "passed", 10),)):
        if project_id not in keys:
            keys[project_id] = make_key(project_id=project_id)[0]
        start = datetime.now(timezone.utc) - timedelta(days=days_ago, minutes=minutes_ago)
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
                             class_name="C", name=name, status=status, duration_ms=duration))
        db.commit()
        return run

    return _seed


def _flip_seed(seed, days_ago):
    for i, status in enumerate(("passed", "failed", "passed", "failed", "passed")):
        seed(days_ago=days_ago, minutes_ago=50 - i, results=(("flipper", status, 1),))


def test_window_up_to_90_days_is_accepted(client, auth, project_role):
    project_role()
    assert client.get(f"{BASE}/flaky?window_days=90", headers=auth()).status_code == 200
    assert client.get(f"{BASE}/flaky?window_days=91", headers=auth()).status_code == 422


def test_fallback_without_rollups_matches_rollup_answer(client, auth, project_role, seed, db):
    project_role()
    _flip_seed(seed, days_ago=40)  # outside 30, inside 90

    before = client.get(f"{BASE}/flaky?window_days=90", headers=auth()).json()
    assert [item["name"] for item in before] == ["flipper"]  # live fallback, full window

    now = datetime.now(timezone.utc)
    for back in range(45):
        upsert_day(db, 1, (now - timedelta(days=back)).date())
    after = client.get(f"{BASE}/flaky?window_days=90", headers=auth()).json()
    assert after == before  # rollup path, same answer


def test_short_window_excludes_old_flips_on_both_paths(client, auth, project_role, seed, db):
    project_role()
    _flip_seed(seed, days_ago=40)
    assert client.get(f"{BASE}/flaky?window_days=14", headers=auth()).json() == []
    now = datetime.now(timezone.utc)
    for back in range(45):
        upsert_day(db, 1, (now - timedelta(days=back)).date())
    assert client.get(f"{BASE}/flaky?window_days=14", headers=auth()).json() == []
