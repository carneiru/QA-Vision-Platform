"""The rollup path must produce exactly what the live path produces: same
flips, pairs, confirmed commits, latest executions — recombined from daily
rows instead of scanning every execution."""

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.analytics.flaky import rank_flaky
from src.ingestion.analytics.rollup import rollup_inputs, upsert_day
from src.ingestion.models import Run, RunResult
from src.ingestion.models.flaky_rollup import FlakyDaily
from src.ingestion.service.analytics_service import flaky_inputs
from src.ingestion.service.ingest_service import test_key as key_of

NOW = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def seed(db, make_key):
    keys = {}

    def _seed(project_id=1, days_ago=0, minutes_ago=0, branch="main", commit_sha=None,
              environment=None, results=(("t1", "passed", 10),)):
        if project_id not in keys:
            keys[project_id] = make_key(project_id=project_id)[0]
        start = NOW - timedelta(days=days_ago, minutes=minutes_ago)
        counts = Counter(status for _, status, _ in results)
        run = Run(project_id=project_id, api_key_id=keys[project_id].id, request_hash="h",
                  ci_provider="local", branch=branch, commit_sha=commit_sha,
                  environment=environment, started_at=start,
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


def _roll_days(db, project_id=1, days=10):
    for back in range(days):
        upsert_day(db, project_id, (NOW - timedelta(days=back)).date())


def _both(db, project_id=1, days=10, branch=None):
    since = NOW - timedelta(days=days)
    live = rank_flaky(*flaky_inputs(db, project_id, since, branch), min_runs=2, min_flip_rate=0.0)
    rolled = rank_flaky(*rollup_inputs(db, project_id, since.date(), branch), min_runs=2, min_flip_rate=0.0)
    return live, rolled


def test_rollup_matches_live_across_day_boundaries(db, seed):
    # Flips that only exist across midnight: P (day 3) -> F (day 2) -> P (day 1)
    seed(days_ago=3, results=(("edge", "passed", 1),))
    seed(days_ago=2, results=(("edge", "failed", 1),))
    seed(days_ago=1, results=(("edge", "passed", 1),))
    # And in-day flips on another branch
    for i, status in enumerate(("passed", "failed", "passed", "failed")):
        seed(days_ago=1, minutes_ago=200 - i, branch="dev", results=(("edge", status, 1),))
    _roll_days(db)

    live, rolled = _both(db)
    assert rolled == live
    assert rolled and rolled[0]["flips"] == live[0]["flips"] > 0


def test_rollup_matches_live_for_confirmed_same_commit(db, seed):
    seed(days_ago=2, minutes_ago=10, commit_sha="aaaaaaa", results=(("conf", "passed", 1),))
    seed(days_ago=1, minutes_ago=5, commit_sha="aaaaaaa", results=(("conf", "failed", 1),))
    _roll_days(db)

    live, rolled = _both(db)
    assert rolled == live
    assert rolled[0]["reason"] == "same_commit"


def test_rollup_excludes_skipped_like_live(db, seed):
    for i, status in enumerate(("passed", "skipped", "failed", "skipped", "passed")):
        seed(days_ago=1, minutes_ago=100 - i, results=(("skippy", status, 1),))
    _roll_days(db)
    live, rolled = _both(db)
    assert rolled == live


def test_rollup_respects_the_branch_filter(db, seed):
    for i, status in enumerate(("passed", "failed", "passed")):
        seed(days_ago=1, minutes_ago=50 - i, branch="main", results=(("t", status, 1),))
    seed(days_ago=1, branch="dev", results=(("t", "failed", 1),))
    _roll_days(db)
    live, rolled = _both(db, branch="main")
    assert rolled == live


def test_upsert_day_is_idempotent(db, seed):
    seed(days_ago=1, results=(("t", "failed", 1),))
    day = (NOW - timedelta(days=1)).date()
    upsert_day(db, 1, day)
    upsert_day(db, 1, day)
    assert db.query(FlakyDaily).filter_by(project_id=1).count() == 1



def test_rollup_ignores_other_projects(db, seed):
    seed(project_id=1, days_ago=1, results=(("mine", "failed", 1),))
    seed(project_id=2, days_ago=1, results=(("theirs", "failed", 1),))
    _roll_days(db, project_id=1)
    _roll_days(db, project_id=2)
    live, rolled = _both(db, project_id=1)
    assert rolled == live
    assert all(item["name"] == "mine" for item in rolled)


def test_job_pass_backfills_and_recomputes_recent_days(db, seed):
    from src.ingestion.jobs.rollup import run_pass

    seed(days_ago=5, results=(("old", "failed", 1),))
    seed(days_ago=0, results=(("fresh", "passed", 1),))

    summary = run_pass(db, now=lambda: NOW)
    assert summary["projects"] == 1
    days = {row.day for row in db.query(FlakyDaily).filter_by(project_id=1)}
    assert (NOW - timedelta(days=5)).date() in days
    assert NOW.date() in days

    # A second pass only revisits today and yesterday.
    summary2 = run_pass(db, now=lambda: NOW)
    assert summary2["days_computed"] == 2

    # A late upload for today lands on the recomputed day.
    seed(days_ago=0, minutes_ago=1, results=(("fresh", "failed", 1),))
    run_pass(db, now=lambda: NOW)
    fresh_key = key_of("s", "C", "fresh")
    row = db.query(FlakyDaily).filter_by(project_id=1, day=NOW.date(), test_key=fresh_key).one()
    assert row.runs == 2 and row.failures == 1
