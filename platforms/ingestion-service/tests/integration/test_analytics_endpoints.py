from collections import Counter
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.ingestion.models import Run, RunResult
from src.ingestion.service.ingest_service import test_key as key_of

BASE = "/api/v1/projects/1/analytics"
ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")


@pytest.fixture
def seed(db, make_key):
    """seed(...) inserts one run with the given results: (name, status, duration_ms) tuples."""
    keys = {}

    def _seed(project_id=1, days_ago=0, minutes_ago=0, branch="main", commit_sha=None, environment=None,
              results=(("t1", "passed", 10),), message=None):
        if project_id not in keys:
            keys[project_id] = make_key(project_id=project_id)[0]
        start = datetime.now(timezone.utc) - timedelta(days=days_ago, minutes=minutes_ago)
        counts = Counter(status for _, status, _ in results)
        run = Run(project_id=project_id, api_key_id=keys[project_id].id, request_hash="h", ci_provider="local",
                  branch=branch, commit_sha=commit_sha, environment=environment, started_at=start,
                  finished_at=start + timedelta(seconds=1), duration_ms=1000, total=len(results),
                  passed=counts["passed"], failed=counts["failed"], skipped=counts["skipped"],
                  errored=counts["errored"], created_at=start)
        db.add(run)
        db.flush()
        for name, status, duration in results:
            db.add(RunResult(run_id=run.id, test_key=key_of("s", "C", name), suite="s", class_name="C", name=name,
                             status=status, duration_ms=duration,
                             message=message if message is not None else (None if status == "passed" else f"{name} {status}")))
        db.commit()
        return run

    return _seed


def get(client, auth, path):
    return client.get(BASE + path, headers=auth())


@pytest.mark.parametrize("role", ALL_ROLES)
@pytest.mark.parametrize("path", ["/trends", "/tests"])
def test_every_reading_role_can_read(client, auth, project_role, role, path):
    project_role(role)
    assert get(client, auth, path).status_code == 200


@pytest.mark.parametrize("path", ["/trends", "/tests"])
def test_access_failures_behave_like_the_run_endpoints(client, auth, project_role, path):
    project_role(status_code=404, body={"detail": "Project not found"})
    assert get(client, auth, path).status_code == 404
    project_role(exc=httpx.ConnectError("refused"))
    assert get(client, auth, path).status_code == 503
    assert client.get(BASE + path).status_code == 401


def test_trends_count_runs_per_day(client, auth, project_role, seed):
    project_role("viewer")
    seed(results=(("a", "passed", 10), ("b", "failed", 20), ("c", "skipped", 0)))
    seed(days_ago=1, results=(("a", "passed", 10),))

    body = get(client, auth, "/trends?days=3").json()

    assert body["tz"] == "UTC" and len(body["days"]) == 3
    before, yesterday, today = body["days"]
    assert (today["runs"], today["total"], today["passed"], today["failed"], today["skipped"]) == (1, 3, 1, 1, 1)
    assert today["pass_rate"] == 0.5 and today["avg_run_duration_ms"] == 1000
    assert yesterday["runs"] == 1 and yesterday["pass_rate"] == 1.0
    assert before["runs"] == 0 and before["pass_rate"] is None


def test_trends_filter_by_branch_and_environment(client, auth, project_role, seed):
    project_role()
    seed(branch="main", environment="staging")
    seed(branch="dev", environment="prod")

    def runs(query):
        return get(client, auth, f"/trends?days=1{query}").json()["days"][0]["runs"]

    assert (runs(""), runs("&branch=main"), runs("&environment=prod"), runs("&branch=main&environment=prod")) == (2, 1, 1, 0)


def test_trends_ignore_other_projects(client, auth, project_role, seed):
    project_role()
    seed(project_id=2)
    assert get(client, auth, "/trends?days=1").json()["days"][0]["runs"] == 0


def test_trends_echo_the_time_zone(client, auth, project_role):
    project_role()
    body = get(client, auth, "/trends?days=7&tz=Europe/Lisbon").json()
    assert body["tz"] == "Europe/Lisbon" and len(body["days"]) == 7


def test_tests_list_counts_and_last_status(client, auth, project_role, seed):
    project_role()
    seed(days_ago=2, results=(("a", "failed", 10), ("b", "passed", 30)))
    seed(days_ago=1, results=(("a", "passed", 20), ("b", "passed", 50)))

    rows = get(client, auth, "/tests").json()

    a = next(r for r in rows if r["name"] == "a")
    assert a["test_key"] == key_of("s", "C", "a")
    assert (a["suite"], a["class_name"]) == ("s", "C")
    assert (a["runs"], a["passed"], a["failed"], a["errored"], a["skipped"]) == (2, 1, 1, 0, 0)
    assert (a["pass_rate"], a["avg_duration_ms"], a["last_status"]) == (0.5, 15, "passed")
    assert a["last_seen"] is not None


def test_tests_sort(client, auth, project_role, seed):
    project_role()
    seed(results=(("slow", "passed", 900), ("flaky", "failed", 10), ("zeta", "passed", 5)))
    seed(results=(("slow", "passed", 900), ("flaky", "errored", 10), ("zeta", "passed", 5)))

    def names(sort):
        return [r["name"] for r in get(client, auth, f"/tests?sort={sort}").json()]

    assert names("failures")[0] == "flaky"
    assert names("duration")[0] == "slow"
    assert names("name") == ["flaky", "slow", "zeta"]


def test_tests_search_matches_literally(client, auth, project_role, seed):
    project_role()
    seed(results=(("100% done", "passed", 1), ("a_b", "passed", 1), ("axb", "passed", 1), ("back\\slash", "passed", 1)))

    def names(term):
        return sorted(r["name"] for r in client.get(BASE + "/tests", params={"search": term}, headers=auth()).json())

    assert names("%") == ["100% done"]
    assert names("a_b") == ["a_b"]
    assert names("\\") == ["back\\slash"]
    assert names("A_B") == ["a_b"]  # case-insensitive


def test_tests_paging(client, auth, project_role, seed):
    project_role()
    seed(results=(("a", "passed", 1), ("b", "passed", 1), ("c", "passed", 1)))
    assert [r["name"] for r in get(client, auth, "/tests?sort=name&limit=2&offset=1").json()] == ["b", "c"]


def test_tests_window(client, auth, project_role, seed):
    project_role()
    seed(days_ago=40, results=(("old", "passed", 1),))
    assert get(client, auth, "/tests?days=30").json() == []
    assert [r["name"] for r in get(client, auth, "/tests?days=60").json()] == ["old"]


@pytest.mark.parametrize("query", [
    "/trends?days=0", "/trends?days=366", "/trends?tz=Not/AZone", "/trends?tz=..%2F..%2Fetc%2Fpasswd",
    "/trends?tz=", "/tests?days=91", "/tests?sort=bogus", "/tests?limit=201", "/tests?offset=-1",
    "/tests?search=" + "x" * 201,
])
def test_invalid_parameters_are_422(client, auth, project_role, query):
    project_role()
    assert get(client, auth, query).status_code == 422
