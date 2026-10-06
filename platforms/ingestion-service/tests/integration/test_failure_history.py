"""Causes over time: is a cause new in this run, or has it been failing for a while?"""
from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.models import Run, RunResult


@pytest.fixture
def run_failing(db, make_key):
    key_row, _ = make_key()
    clock = [datetime(2026, 10, 1, tzinfo=timezone.utc)]

    def _make(*messages, branch="main", project_id=1):
        clock[0] += timedelta(hours=1)
        run = Run(project_id=project_id, api_key_id=key_row.id, request_hash="h", ci_provider="local", branch=branch,
                  started_at=clock[0], finished_at=clock[0] + timedelta(minutes=1), duration_ms=60000,
                  total=max(len(messages), 1), passed=0 if messages else 1, failed=len(messages), skipped=0,
                  errored=0, created_at=clock[0])
        db.add(run)
        db.flush()
        for i, message in enumerate(messages):
            db.add(RunResult(run_id=run.id, test_key=f"{i:064d}", suite="s", class_name="C", name=f"t{i}",
                             status="failed", duration_ms=1, message=message))
        if not messages:
            db.add(RunResult(run_id=run.id, test_key="0" * 64, suite="s", class_name="C", name="t", status="passed",
                             duration_ms=1))
        db.commit()
        return run

    return _make


def groups(client, auth, run):
    return {g["headline"]: g["history"] for g in
            client.get(f"/api/v1/runs/{run.id}/failure-groups", headers=auth()).json()["groups"]}


def test_a_cause_seen_for_the_first_time_is_new(client, auth, project_role, run_failing):
    run_failing("Old: boom 1")
    head = run_failing("Old: boom 2", "New: kaput")
    project_role("viewer")
    h = groups(client, auth, head)
    assert h["New: kaput"] == {"window": 2, "seen_in": 1, "streak": 1, "since_run_id": head.id,
                               "since_started_at": h["New: kaput"]["since_started_at"]}
    assert h["Old: boom 2"]["seen_in"] == 2 and h["Old: boom 2"]["streak"] == 2


def test_streak_counts_consecutive_runs_and_seen_in_counts_the_window(client, auth, project_role, run_failing):
    first = run_failing("Flaky: x")
    run_failing()                       # a green run breaks the streak
    second = run_failing("Flaky: x")
    head = run_failing("Flaky: x")
    project_role("viewer")
    h = groups(client, auth, head)["Flaky: x"]
    assert (h["window"], h["seen_in"], h["streak"], h["since_run_id"]) == (4, 3, 2, second.id)
    assert first.id != h["since_run_id"]


def test_only_the_same_branch_and_earlier_runs_count(client, auth, project_role, run_failing):
    run_failing("Boom", branch="feature/x")
    head = run_failing("Boom")
    run_failing("Boom")                 # later than head: not history
    project_role("viewer")
    assert groups(client, auth, head)["Boom"]["window"] == 1


def test_the_window_is_twenty_runs(client, auth, project_role, run_failing):
    for _ in range(25):
        head = run_failing("Boom")
    project_role("viewer")
    h = groups(client, auth, head)["Boom"]
    assert (h["window"], h["seen_in"], h["streak"]) == (20, 20, 20)
