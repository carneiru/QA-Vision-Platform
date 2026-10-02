"""Per-branch aggregates for the branch-comparison view."""

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.models import Run, RunResult
from src.ingestion.service.ingest_service import test_key as key_of

BASE = "/api/v1/projects/1/analytics"


@pytest.fixture
def seed(db, make_key):
    keys = {}

    def _seed(project_id=1, days_ago=0, branch="main", results=(("t1", "passed", 10),)):
        if project_id not in keys:
            keys[project_id] = make_key(project_id=project_id)[0]
        start = datetime.now(timezone.utc) - timedelta(days=days_ago)
        counts = Counter(status for _, status, _ in results)
        run = Run(project_id=project_id, api_key_id=keys[project_id].id, request_hash="h",
                  ci_provider="local", branch=branch, started_at=start,
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


def test_branches_aggregate_per_branch(client, auth, project_role, seed):
    project_role()
    seed(branch="main", results=(("a", "passed", 1), ("b", "failed", 1)))
    seed(branch="main", results=(("a", "passed", 1), ("b", "passed", 1)))
    seed(branch="dev", results=(("a", "skipped", 1),))

    response = client.get(f"{BASE}/branches", headers=auth())
    assert response.status_code == 200, response.text
    by_branch = {row["branch"]: row for row in response.json()}
    assert set(by_branch) == {"main", "dev"}

    main = by_branch["main"]
    assert (main["runs"], main["passed"], main["failed"]) == (2, 3, 1)
    assert main["pass_rate"] == 0.75

    dev = by_branch["dev"]
    assert dev["runs"] == 1
    assert dev["pass_rate"] is None  # only skipped results


def test_branches_most_recent_first_and_window(client, auth, project_role, seed):
    project_role()
    seed(days_ago=2, branch="old-but-in-window")
    seed(days_ago=0, branch="fresh")
    seed(days_ago=40, branch="stale")

    rows = client.get(f"{BASE}/branches?days=30", headers=auth()).json()
    assert [r["branch"] for r in rows] == ["fresh", "old-but-in-window"]


def test_branches_null_branch_is_returned_as_null(client, auth, project_role, seed):
    project_role()
    seed(branch=None)
    rows = client.get(f"{BASE}/branches", headers=auth()).json()
    assert [r["branch"] for r in rows] == [None]


def test_branches_ignore_other_projects(client, auth, project_role, seed):
    project_role()
    seed(project_id=1, branch="mine")
    seed(project_id=2, branch="theirs")
    rows = client.get(f"{BASE}/branches", headers=auth()).json()
    assert [r["branch"] for r in rows] == ["mine"]


def test_branches_invalid_parameters_are_422(client, auth, project_role):
    project_role()
    assert client.get(f"{BASE}/branches?days=0", headers=auth()).status_code == 422
    assert client.get(f"{BASE}/branches?limit=0", headers=auth()).status_code == 422
