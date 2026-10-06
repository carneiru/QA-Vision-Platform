"""Comparing two runs: what broke, what got fixed, what got slower."""
from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.models import Run, RunResult


@pytest.fixture
def run_with(db, make_key):
    key_row, _ = make_key()
    clock = [datetime(2026, 10, 1, tzinfo=timezone.utc)]

    def _make(results, project_id=1, branch="main"):
        """results: {name: (status, duration_ms)} or a list of (name, status, duration_ms) for repeats."""
        items = results.items() if isinstance(results, dict) else [(n, (s, d)) for n, s, d in results]
        items = list(items)
        clock[0] += timedelta(hours=1)
        statuses = [s for _, (s, _) in items]
        run = Run(project_id=project_id, api_key_id=key_row.id, request_hash="h", ci_provider="local", branch=branch,
                  started_at=clock[0], finished_at=clock[0] + timedelta(minutes=1), duration_ms=60000,
                  total=len(statuses), passed=statuses.count("passed"), failed=statuses.count("failed"),
                  skipped=statuses.count("skipped"), errored=statuses.count("errored"), created_at=clock[0])
        db.add(run)
        db.flush()
        for name, (status, duration) in items:
            db.add(RunResult(run_id=run.id, test_key=name.rjust(64, "0")[-64:], suite="s", class_name="C", name=name,
                             status=status, duration_ms=duration, message=f"{name} broke" if status != "passed" else None))
        db.commit()
        return run

    return _make


def compare(client, auth, base, head):
    return client.get(f"/api/v1/runs/{head.id}/compare/{base.id}", headers=auth())


def test_compare_sorts_tests_into_what_changed(client, auth, project_role, run_with):
    base = run_with({"stays green": ("passed", 100), "breaks": ("passed", 100), "gets fixed": ("failed", 100),
                     "stays red": ("failed", 100), "goes away": ("passed", 100), "slows down": ("passed", 1000),
                     "gets skipped": ("passed", 100)})
    head = run_with({"stays green": ("passed", 110), "breaks": ("errored", 100), "gets fixed": ("passed", 100),
                     "stays red": ("failed", 100), "is new": ("failed", 100), "slows down": ("passed", 4000),
                     "gets skipped": ("skipped", 0)})
    project_role("viewer")
    response = compare(client, auth, base, head)
    assert response.status_code == 200, response.text
    body = response.json()
    names = {k: [t["name"] for t in body[k]] for k in ("new_failures", "fixed", "still_failing", "added", "removed", "slower")}
    assert names == {"new_failures": ["breaks"], "fixed": ["gets fixed"], "still_failing": ["stays red"],
                     "added": ["is new"], "removed": ["goes away"], "slower": ["slows down"]}
    assert body["base"]["id"] == base.id and body["head"]["id"] == head.id
    broke = body["new_failures"][0]
    assert (broke["base_status"], broke["head_status"], broke["message"]) == ("passed", "errored", "breaks broke")
    slow = body["slower"][0]
    assert (slow["base_duration_ms"], slow["head_duration_ms"]) == (1000, 4000)
    assert body["counts"] == {"new_failures": 1, "fixed": 1, "still_failing": 1, "added": 1, "removed": 1,
                              "slower": 1, "unchanged": 2}


def test_small_or_relative_slowdowns_are_not_reported(client, auth, project_role, run_with):
    base = run_with({"fast": ("passed", 100), "steady": ("passed", 10000)})
    head = run_with({"fast": ("passed", 900), "steady": ("passed", 14000)})   # +800 ms; +40 %
    project_role("viewer")
    assert compare(client, auth, base, head).json()["slower"] == []


def test_a_repeated_test_counts_by_its_last_attempt(client, auth, project_role, run_with):
    base = run_with([("retried", "passed", 10)])
    head = run_with([("retried", "failed", 10), ("retried", "passed", 12)])   # failed, then passed on retry
    project_role("viewer")
    body = compare(client, auth, base, head).json()
    assert body["new_failures"] == [] and body["counts"]["unchanged"] == 1


def test_runs_of_different_projects_cannot_be_compared(client, auth, project_role, run_with):
    base = run_with({"t": ("passed", 1)}, project_id=2)
    head = run_with({"t": ("passed", 1)})
    project_role("viewer")
    response = compare(client, auth, base, head)
    assert response.status_code == 404 and response.json()["detail"] == "Run not found"


def test_missing_runs_and_unseen_projects_are_404(client, auth, project_role, run_with):
    head = run_with({"t": ("passed", 1)}, project_id=3)
    base = run_with({"t": ("passed", 1)}, project_id=3)
    assert client.get(f"/api/v1/runs/{head.id}/compare/999999", headers=auth()).status_code == 404
    project_role(project_id=3, status_code=404, body={"detail": "Project not found"})
    assert compare(client, auth, base, head).status_code == 404


def test_lists_are_capped_but_counts_are_not(client, auth, project_role, run_with):
    base = run_with({f"t{i}": ("passed", 1) for i in range(250)})
    head = run_with({f"t{i}": ("failed", 1) for i in range(250)})
    project_role("viewer")
    body = compare(client, auth, base, head).json()
    assert body["counts"]["new_failures"] == 250 and len(body["new_failures"]) == 200
