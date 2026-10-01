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


# ---- history ------------------------------------------------------------------------------

def test_history_newest_first_with_limit_and_summary(client, auth, project_role, seed):
    project_role()
    for days_ago, status in ((3, "passed"), (2, "failed"), (1, "passed")):
        seed(days_ago=days_ago, commit_sha=f"c0ffee{days_ago}", results=(("a", status, 10 * days_ago),))
    key = key_of("s", "C", "a")

    body = get(client, auth, f"/tests/{key}/history?limit=2").json()

    assert (body["test_key"], body["suite"], body["class_name"], body["name"]) == (key, "s", "C", "a")
    assert [e["duration_ms"] for e in body["executions"]] == [10, 20]
    assert [e["commit_sha"] for e in body["executions"]] == ["c0ffee1", "c0ffee2"]
    assert body["summary"] == {"runs": 3, "passed": 2, "failed": 1, "errored": 0, "skipped": 0,
                               "pass_rate": 0.6667, "avg_duration_ms": 20}


def test_history_cuts_the_message_to_500_characters(client, auth, project_role, seed):
    project_role()
    seed(results=(("a", "failed", 1),), message="x" * 800)
    body = get(client, auth, f"/tests/{key_of('s', 'C', 'a')}/history").json()
    assert body["executions"][0]["message"] == "x" * 500


def test_history_filters_by_branch(client, auth, project_role, seed):
    project_role()
    seed(branch="main", results=(("a", "passed", 1),))
    seed(branch="dev", results=(("a", "failed", 1),))
    body = get(client, auth, f"/tests/{key_of('s', 'C', 'a')}/history?branch=dev").json()
    assert [e["status"] for e in body["executions"]] == ["failed"]
    assert body["summary"]["runs"] == 1


def test_history_of_an_unknown_test_is_404(client, auth, project_role):
    project_role()
    response = get(client, auth, f"/tests/{'0' * 64}/history")
    assert response.status_code == 404
    assert response.json() == {"detail": "Test not found"}


def test_history_of_another_projects_test_is_404(client, auth, project_role, seed):
    project_role()
    seed(project_id=2, results=(("a", "passed", 1),))
    assert get(client, auth, f"/tests/{key_of('s', 'C', 'a')}/history").status_code == 404


def test_history_of_a_known_test_outside_the_window_is_empty(client, auth, project_role, seed):
    project_role()
    seed(days_ago=40, results=(("a", "passed", 1),))
    body = get(client, auth, f"/tests/{key_of('s', 'C', 'a')}/history?days=30").json()
    assert body["executions"] == [] and body["name"] == "a"
    assert body["summary"] == {"runs": 0, "passed": 0, "failed": 0, "errored": 0, "skipped": 0,
                               "pass_rate": None, "avg_duration_ms": None}


@pytest.mark.parametrize("bad_key", ["xyz", "A" * 64, "0" * 63])
def test_history_rejects_a_malformed_key(client, auth, project_role, bad_key):
    project_role()
    assert get(client, auth, f"/tests/{bad_key}/history").status_code == 422


# ---- flaky --------------------------------------------------------------------------------

@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_reading_role_can_read_flaky(client, auth, project_role, role):
    project_role(role)
    assert get(client, auth, "/flaky").status_code == 200


def test_flaky_end_to_end(client, auth, project_role, seed):
    project_role()
    # confirmed: a pass and a fail on one commit, one environment
    seed(minutes_ago=60, commit_sha="aaaaaaa", results=(("confirmed", "passed", 1),))
    seed(minutes_ago=59, commit_sha="aaaaaaa", results=(("confirmed", "failed", 1),))
    # suspected: flips on main, no commit
    for i, status in enumerate(("passed", "failed", "passed", "failed", "passed")):
        seed(minutes_ago=50 - i, results=(("flipper", status, 1),))
    # an environment-specific failure: not confirmed, and too few runs to count as flips
    seed(minutes_ago=40, commit_sha="bbbbbbb", environment="py39", results=(("envbug", "failed", 1),))
    seed(minutes_ago=39, commit_sha="bbbbbbb", environment="py312", results=(("envbug", "passed", 1),))
    # errored -> failed is not a flip
    for i, status in enumerate(("failed", "errored", "failed", "errored", "failed")):
        seed(minutes_ago=30 - i, results=(("broken", status, 1),))
    # skipped results are ignored: P S F S P S F S P is 5 runs with 4 flips
    for i, status in enumerate(("passed", "skipped", "failed", "skipped", "passed", "skipped", "failed", "skipped",
                                "passed")):
        seed(minutes_ago=20 - i, results=(("skippy", status, 1),))

    items = get(client, auth, "/flaky").json()

    # confirmed first; then flip rate 1.0 for both, the more recently seen first
    assert [(i["name"], i["reason"]) for i in items] == [("confirmed", "same_commit"), ("skippy", "flips"),
                                                         ("flipper", "flips")]
    assert items[0]["commits"] == [{"commit_sha": "aaaaaaa", "environment": None}]
    skippy = items[1]
    assert (skippy["runs"], skippy["flips"], skippy["flip_rate"], skippy["last_status"]) == (5, 4, 1.0, "passed")


def test_flips_are_counted_per_branch(client, auth, project_role, seed):
    project_role()
    # interleaved: main P, dev P, main P, dev F, main P -> per branch 1 flip in 3 pairs (0.3333);
    # counted across the interleaved stream it would be 2 in 4 (0.5)
    for i, (branch, status) in enumerate((("main", "passed"), ("dev", "passed"), ("main", "passed"),
                                          ("dev", "failed"), ("main", "passed"))):
        seed(minutes_ago=10 - i, branch=branch, results=(("t", status, 1),))
    items = get(client, auth, "/flaky").json()
    assert [(i["name"], i["flips"], i["flip_rate"]) for i in items] == [("t", 1, 0.3333)]


def test_flaky_filters_by_branch_and_window(client, auth, project_role, seed):
    project_role()
    for i, status in enumerate(("passed", "failed", "passed", "failed", "passed")):
        seed(days_ago=20, minutes_ago=i, results=(("old", status, 1),))
    for i, status in enumerate(("passed", "failed", "passed", "failed", "passed")):
        seed(minutes_ago=10 - i, branch="dev", results=(("devonly", status, 1),))

    assert [i["name"] for i in get(client, auth, "/flaky").json()] == ["devonly"]          # 14-day window
    assert sorted(i["name"] for i in get(client, auth, "/flaky?window_days=30").json()) == ["devonly", "old"]
    assert get(client, auth, "/flaky?branch=main").json() == []


@pytest.mark.parametrize("query", ["/flaky?window_days=0", "/flaky?window_days=31", "/flaky?min_runs=1",
                                   "/flaky?min_runs=1001", "/flaky?min_flip_rate=1.5", "/flaky?min_flip_rate=-0.1",
                                   "/tests/" + "0" * 64 + "/history?days=91", "/tests/" + "0" * 64 + "/history?limit=501"])
def test_invalid_history_and_flaky_parameters_are_422(client, auth, project_role, query):
    project_role()
    assert get(client, auth, query).status_code == 422


def test_a_pass_and_a_fail_inside_one_run_is_not_same_commit(client, auth, project_role, seed):
    # Same name twice in one run (e.g. two parametrizations sharing a name): not a re-run of the
    # code, so not evidence of flakiness. Only commits with at least two runs are compared, which
    # is also what keeps this query from grouping every result row.
    project_role()
    seed(commit_sha="ccccccc", results=(("dup", "passed", 1), ("dup", "failed", 1)))
    assert get(client, auth, "/flaky").json() == []


def test_same_commit_needs_a_second_run_of_that_commit(client, auth, project_role, seed):
    project_role()
    seed(commit_sha="ddddddd", results=(("t", "passed", 1),))
    seed(commit_sha="eeeeeee", results=(("t", "failed", 1),))
    assert get(client, auth, "/flaky").json() == []
    seed(commit_sha="ddddddd", results=(("t", "failed", 1),))
    items = get(client, auth, "/flaky").json()
    assert [(i["reason"], i["commits"]) for i in items] == [("same_commit", [{"commit_sha": "ddddddd", "environment": None}])]


# ---- found by the final review ------------------------------------------------------------

@pytest.mark.parametrize("query", ["/trends?tz=America", "/trends?tz=Etc", "/tests?offset=10000000000000000000000000"])
def test_more_invalid_parameters_are_422(client, auth, project_role, query):
    project_role()
    assert get(client, auth, query).status_code == 422


@pytest.mark.parametrize("path, name", [("/trends", "branch"), ("/trends", "environment"), ("/tests", "search"),
                                        ("/flaky", "branch")])
def test_a_nul_character_is_422(client, auth, project_role, path, name):
    # PostgreSQL cannot take NUL in a string parameter; SQLite (these tests) would not notice
    project_role()
    assert client.get(BASE + path, params={name: "a\x00b"}, headers=auth()).status_code == 422


def test_an_empty_filter_means_no_filter(client, auth, project_role, seed):
    project_role()
    seed(branch="main", environment="staging")
    assert get(client, auth, "/trends?days=1&branch=&environment=").json()["days"][0]["runs"] == 1
    for i, status in enumerate(("passed", "failed", "passed", "failed", "passed")):
        seed(minutes_ago=10 - i, results=(("flipper", status, 1),))
    assert [i["name"] for i in get(client, auth, "/flaky?branch=").json()] == ["flipper"]


def test_duplicates_in_one_run_are_not_same_commit_even_with_another_shard(client, auth, project_role, seed):
    # Two shards of one commit: the duplicate pass/fail is inside one of them only
    project_role()
    seed(commit_sha="ccccccc", results=(("dup", "passed", 1), ("dup", "failed", 1)))
    seed(commit_sha="ccccccc", results=(("other", "passed", 1),))
    assert get(client, auth, "/flaky").json() == []
