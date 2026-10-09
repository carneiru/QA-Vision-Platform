"""Sections tests and duration (spec: Section tests (P3), Section duration (P3))."""
from datetime import datetime, timezone

import pytest

from conftest import post_report, report_key


def at(month, day, hour=10):
    return datetime(2026, month, day, hour, tzinfo=timezone.utc)


@pytest.fixture
def seeded(project_role, report_now, seed_run):
    project_role()
    seed_run(at(9, 26), results=(("t1", "failed", 5),), duration_ms=5000)                       # previous period
    seed_run(at(10, 2), results=(("t1", "passed", 100), ("t2", "failed", 300), ("t3", "skipped", 0)), duration_ms=1000)
    seed_run(at(10, 3), results=(("t1", "failed", 120), ("t2", "passed", 200)), duration_ms=3000)
    seed_run(at(10, 3, 12), branch="dev", results=(("t1", "passed", 90),), duration_ms=2000)
    seed_run(at(10, 4), results=(("t1", "passed", 110),), duration_ms=4000)


def section(client, auth, name, **body):
    response = post_report(client, auth, sections=[name], **body)
    assert response.status_code == 200, response.text
    return response.json()[name]


def test_tests_rows_are_columnar(client, auth, seeded):
    t = section(client, auth, "tests")
    assert t["columns"] == ["test_key", "executions", "passed", "failed", "errored", "skipped", "flips", "pairs",
                            "duration_ms_sum", "last_status"]
    rows = {r[0]: dict(zip(t["columns"], r)) for r in t["rows"]}
    t1 = rows[report_key("t1")]
    # main: P(10-2) F(10-3) P(10-4) = 2 flips over 2 pairs; dev: one outcome = 0 pairs
    assert (t1["executions"], t1["passed"], t1["failed"], t1["flips"], t1["pairs"]) == (4, 3, 1, 2, 2)
    assert (t1["duration_ms_sum"], t1["last_status"]) == (420, "passed")
    t3 = rows[report_key("t3")]
    assert (t3["skipped"], t3["pairs"], t3["flips"], t3["last_status"]) == (1, 0, 0, "skipped")
    assert len(rows) == 3 and t["truncated"] is False
    assert [r[0] for r in t["rows"]] == sorted(rows)                    # by test key when not truncated


def test_tests_truncate_to_the_most_failing(client, auth, seeded, monkeypatch):
    from src.ingestion.service import report_service
    monkeypatch.setattr(report_service, "TESTS_ROW_CAP", 1)
    t = section(client, auth, "tests")
    assert t["truncated"] is True and len(t["rows"]) == 1
    assert t["rows"][0][0] in {report_key("t1"), report_key("t2")}      # a test with one failure, not t3


def test_tests_honour_test_keys(client, auth, seeded):
    assert [r[0] for r in section(client, auth, "tests", test_keys=[report_key("t2")])["rows"]] == [report_key("t2")]


def _seed_story(seed_run, name, statuses, branch="main", start_day=1):
    for day, status in enumerate(statuses, start=start_day):
        seed_run(at(10, day), branch=branch, results=((name, status, 1),))


def _flips_by_definition(db):
    """Ground truth: the last non-skipped attempt per (test, run), per branch in (started_at, run_id) order."""
    from src.ingestion.models import Run, RunResult
    last = {}
    for row, run in (db.query(RunResult, Run).join(Run, Run.id == RunResult.run_id)
                     .filter(RunResult.status != "skipped").order_by(RunResult.id)):
        last[(row.test_key, run.branch, run.started_at, run.id)] = row.status == "passed"
    stories = {}
    for (key, branch, started, run_id), passed in sorted(last.items(), key=lambda kv: (kv[0][2], kv[0][3])):
        stories.setdefault((key, branch), []).append(passed)
    out = {}
    for (key, _), story in stories.items():
        out[key] = out.get(key, 0) + sum(1 for a, b in zip(story, story[1:]) if a != b)
    return out


def _flips(client, auth):
    t = section(client, auth, "tests", to="2026-10-09")
    return {r[0]: dict(zip(t["columns"], r))["flips"] for r in t["rows"]}


def test_flips_when_every_pass_is_isolated(client, auth, project_role, report_now, seed_run):
    project_role()
    _seed_story(seed_run, "a", ("passed", "failed", "passed", "failed", "passed", "failed", "passed"))
    assert _flips(client, auth)[report_key("a")] == 6


def test_flips_with_long_pass_runs_on_both_sides(client, auth, project_role, report_now, seed_run):
    project_role()
    _seed_story(seed_run, "b", ("passed", "passed", "failed", "passed", "passed", "passed", "failed", "passed", "passed"))
    assert _flips(client, auth)[report_key("b")] == 4


def test_flips_are_counted_per_branch(client, auth, project_role, report_now, seed_run):
    project_role()
    seed_run(at(10, 1), branch="main", results=(("c", "passed", 1),))
    seed_run(at(10, 2), branch="dev", results=(("c", "passed", 1),))
    seed_run(at(10, 3), branch="main", results=(("c", "failed", 1),))
    seed_run(at(10, 4), branch="dev", results=(("c", "passed", 1),))
    seed_run(at(10, 5), branch="main", results=(("c", "passed", 1),))
    assert _flips(client, auth)[report_key("c")] == 2   # main P F P; dev P P: never main-next-to-dev


def test_flips_with_a_retried_run_whose_last_attempt_passes(client, auth, db, project_role, report_now, seed_run):
    project_role()
    seed_run(at(10, 1), results=(("r", "passed", 1),))
    seed_run(at(10, 2), results=(("r", "failed", 1), ("r", "passed", 1)))   # outcome: passed (P P F F P = 2 flips)
    seed_run(at(10, 3), results=(("r", "failed", 1),))
    seed_run(at(10, 4), results=(("r", "passed", 1), ("r", "failed", 1)))   # outcome: failed
    seed_run(at(10, 5), results=(("r", "passed", 1),))
    assert _flips(client, auth)[report_key("r")] == 2 == _flips_by_definition(db)[report_key("r")]


@pytest.mark.parametrize("seed", range(6))
def test_section_flips_equal_the_flips_over_every_outcome(client, auth, db, project_role, report_now, seed_run, seed):
    import random
    rng = random.Random(seed)
    project_role()
    for _ in range(25):
        results = []
        for name in ("t0", "t1", "t2", "t3"):
            for _ in range(rng.choice((0, 1, 1, 1, 2))):
                results.append((name, rng.choices(("passed", "failed", "errored", "skipped"), (60, 20, 5, 15))[0], 1))
        seed_run(at(10, rng.randint(1, 6), rng.randint(0, 23)), branch=rng.choice(("main", "main", "dev", None)),
                 results=tuple(results) or (("t0", "passed", 1),))
    truth = _flips_by_definition(db)
    got = _flips(client, auth)
    assert {k: v for k, v in got.items() if v or truth.get(k)} == {k: v for k, v in truth.items() if v}


def test_duration_is_run_wall_time_without_keys(client, auth, seeded):
    d = section(client, auth, "duration")
    assert d["basis"] == "run_wall_time" and len(d["buckets"]) == 7
    by_day = {b["date"]: b for b in d["buckets"]}
    assert by_day["2026-10-03"] == {"date": "2026-10-03", "runs": 2, "avg_ms": 2500, "p50_ms": 2500, "p90_ms": 2900, "max_ms": 3000}
    assert by_day["2026-10-01"] == {"date": "2026-10-01", "runs": 0, "avg_ms": None, "p50_ms": None, "p90_ms": None, "max_ms": None}
    assert d["previous"] == {"runs": 1, "avg_ms": 5000, "p50_ms": 5000, "p90_ms": 5000}


def test_duration_with_keys_is_time_in_those_tests(client, auth, seeded):
    d = section(client, auth, "duration", test_keys=[report_key("t1")])
    assert d["basis"] == "test_time"
    by_day = {b["date"]: b for b in d["buckets"]}
    assert (by_day["2026-10-03"]["runs"], by_day["2026-10-03"]["max_ms"]) == (2, 120)    # 120 on main, 90 on dev
    assert d["previous"]["avg_ms"] == 5


def test_duration_previous_is_null_without_runs(client, auth, seeded):
    assert section(client, auth, "duration", branch="dev")["previous"] is None
