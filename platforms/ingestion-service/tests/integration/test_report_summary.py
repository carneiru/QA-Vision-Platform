"""Section summary (spec: Section summary (P1); Ruling 2: previous_buckets)."""
from datetime import datetime, timezone

import pytest

from conftest import post_report, report_key


def at(day, hour=10):
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


@pytest.fixture
def seeded(project_role, report_now, seed_run):
    project_role()
    seed_run(at(2), results=(("t1", "passed", 100), ("t2", "failed", 300), ("t3", "skipped", 0)), duration_ms=1000)
    seed_run(at(5), results=(("t1", "passed", 120), ("t2", "passed", 280)), duration_ms=3000)
    seed_run(at(6), branch="dev", environment="staging", results=(("t1", "errored", 50),), duration_ms=2000)
    seed_run(datetime(2026, 9, 25, 10, tzinfo=timezone.utc), results=(("t1", "passed", 1), ("t2", "passed", 1)),
             duration_ms=2000)
    seed_run(at(3), project_id=2, results=(("t9", "failed", 1),))


def summary(client, auth, **body):
    response = post_report(client, auth, **body)
    assert response.status_code == 200, response.text
    return response.json()["summary"]


def test_current_and_previous_totals(client, auth, seeded):
    s = summary(client, auth)
    assert s["current"] == {"runs": 3, "executions": 6, "passed": 3, "failed": 1, "errored": 1, "skipped": 1,
                            "pass_rate": 0.6, "tests": 3, "failing_tests": 2, "avg_run_duration_ms": 2000}
    assert s["previous"] == {"runs": 1, "executions": 2, "passed": 2, "failed": 0, "errored": 0, "skipped": 0,
                             "pass_rate": 1.0, "tests": 2, "failing_tests": 0, "avg_run_duration_ms": 2000}


def test_previous_is_null_when_the_previous_period_has_no_runs(client, auth, seeded):
    assert summary(client, auth, branch="dev")["previous"] is None


def test_buckets_cover_every_day_with_zeros(client, auth, seeded):
    buckets = summary(client, auth)["buckets"]
    assert [b["date"] for b in buckets] == [f"2026-10-0{d}" for d in range(1, 8)]
    assert buckets[0] == {"date": "2026-10-01", "runs": 0, "executions": 0, "passed": 0, "failed": 0,
                          "errored": 0, "skipped": 0, "pass_rate": None}
    assert (buckets[1]["runs"], buckets[1]["executions"], buckets[1]["pass_rate"]) == (1, 3, 0.5)
    assert (buckets[5]["errored"], buckets[5]["pass_rate"]) == (1, 0.0)


def test_previous_buckets_align_bucket_by_bucket(client, auth, seeded):
    prev = summary(client, auth)["previous_buckets"]
    assert len(prev) == 7
    assert prev[1]["date"] == "2026-09-25" and prev[1]["runs"] == 1 and prev[1]["pass_rate"] == 1.0
    assert sum(b["runs"] for b in prev) == 1


def test_top_failing_lists_only_tests_that_failed_and_slowest_by_average(client, auth, seeded):
    s = summary(client, auth)
    failing = {r["name"]: r for r in s["top_failing"]}
    assert set(failing) == {"t1", "t2"}
    assert failing["t2"] == {"test_key": report_key("t2"), "suite": "s", "class_name": "C", "name": "t2",
                             "executions": 2, "failures": 1, "pass_rate": 0.5}
    assert [r["name"] for r in s["slowest"]][:2] == ["t2", "t1"]
    assert s["slowest"][0]["avg_duration_ms"] == 290


def test_branches_by_runs_and_facets_ignore_other_filters(client, auth, seeded):
    s = summary(client, auth, branch="main")
    assert [(b["branch"], b["runs"]) for b in s["branches"]] == [("main", 2)]
    assert s["facets"] == {"branches": ["main", "dev"], "environments": ["staging"], "ci_providers": ["local"]}
    assert s["current"]["runs"] == 2


def test_test_keys_narrow_every_figure(client, auth, seeded):
    s = summary(client, auth, test_keys=[report_key("t2")])
    assert (s["current"]["runs"], s["current"]["executions"], s["current"]["failing_tests"]) == (2, 2, 1)
    assert [r["name"] for r in s["top_failing"]] == ["t2"]


def test_a_retry_counts_every_row(client, auth, project_role, report_now, seed_run):
    project_role()
    seed_run(at(2), results=(("t1", "failed", 10), ("t1", "passed", 10)))
    s = summary(client, auth)
    assert (s["current"]["executions"], s["current"]["failed"], s["current"]["passed"]) == (2, 1, 1)
    assert s["current"]["failing_tests"] == 1


def test_an_empty_period(client, auth, project_role, report_now):
    project_role()
    s = summary(client, auth)
    assert s["current"]["runs"] == 0 and s["current"]["pass_rate"] is None
    assert s["current"]["avg_run_duration_ms"] is None and s["previous"] is None
    assert s["top_failing"] == [] and s["branches"] == [] and len(s["buckets"]) == 7
