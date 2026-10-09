"""Section regressions (spec: Section regressions (P2))."""
from datetime import datetime, timezone

import pytest

from conftest import post_report

DAY = 86_400_000


def at(month, day):
    return datetime(2026, month, day, 10, tzinfo=timezone.utc)


@pytest.fixture
def seeded(project_role, report_now, seed_run):
    project_role()
    seed_run(at(9, 24), results=(("t2", "passed", 1),))
    seed_run(at(9, 25), results=(("t1", "passed", 1), ("t2", "failed", 1), ("t3", "failed", 1)))
    seed_run(at(10, 2), results=(("t1", "failed", 1, "AssertionError: x"), ("t2", "passed", 1), ("t3", "failed", 1),
                                 ("t5", "failed", 1)))
    seed_run(at(10, 3), results=(("t1", "failed", 1, "AssertionError: y"), ("t2", "passed", 1), ("t3", "failed", 1),
                                 ("t4", "skipped", 0)))
    seed_run(at(10, 4), results=(("t5", "failed", 1), ("t5", "passed", 1)))   # a retry: the later row wins
    seed_run(at(10, 5), branch="dev", results=(("t1", "passed", 1),))


def regressions(client, auth, **body):
    response = post_report(client, auth, sections=["regressions"], **body)
    assert response.status_code == 200, response.text
    return response.json()["regressions"]


def test_newly_failing_fixed_and_longest(client, auth, seeded):
    r = regressions(client, auth)
    assert r["newly_failing"]["total"] == 1
    (newly,) = r["newly_failing"]["items"]
    assert (newly["name"], newly["branch"], newly["failures"], newly["headline"]) == ("t1", "main", 2, "AssertionError: y")
    assert (newly["failing_since"], newly["last_passed_at"]) == ("2026-10-02T10:00:00Z", "2026-09-25T10:00:00Z")
    fixed = {f["name"]: f for f in r["fixed"]["items"]}
    assert set(fixed) == {"t2", "t5"}
    assert fixed["t2"]["time_to_fix_ms"] == 7 * DAY and fixed["t2"]["failing_since_bounded"] is False
    assert fixed["t5"]["fixed_at"] == "2026-10-04T10:00:00Z" and fixed["t5"]["failing_since_bounded"] is True
    longest = r["longest_failing"]["items"]
    assert [(i["name"], i["failing_since_bounded"]) for i in longest] == [("t3", True), ("t1", False)]
    assert longest[0]["failing_since"] == "2026-09-24T00:00:00Z" and longest[0]["consecutive_failures"] == 3


def test_time_to_fix(client, auth, seeded):
    assert regressions(client, auth)["time_to_fix"] == {"fixes": 2, "mean_ms": int(4.5 * DAY), "median_ms": int(4.5 * DAY),
                                                         "p90_ms": int(6.5 * DAY), "bounded": 1}


def test_flakiness_per_bucket(client, auth, seeded):
    days = {d["date"]: d for d in regressions(client, auth)["flakiness"]}
    assert len(days) == 7
    assert (days["2026-10-02"]["flips"], days["2026-10-02"]["flaky_tests"], days["2026-10-02"]["tests_executed"]) == (2, 2, 4)
    assert days["2026-10-03"]["tests_executed"] == 3                    # t4 was only skipped
    assert (days["2026-10-04"]["flips"], days["2026-10-04"]["tests_executed"]) == (1, 1)
    assert days["2026-10-05"]["flaky_tests"] == 0                       # dev's first outcome is no flip


def test_a_branch_filter_and_test_keys(client, auth, seeded):
    from conftest import report_key
    assert regressions(client, auth, branch="dev")["newly_failing"]["total"] == 0
    only_t3 = regressions(client, auth, test_keys=[report_key("t3")])
    assert only_t3["fixed"]["total"] == 0 and [i["name"] for i in only_t3["longest_failing"]["items"]] == ["t3"]


def test_list_caps(client, auth, seeded, monkeypatch):
    from src.ingestion.service import report_service
    monkeypatch.setattr(report_service, "MAX_FIXED", 1)
    fixed = regressions(client, auth)["fixed"]
    assert fixed["total"] == 2 and len(fixed["items"]) == 1


def test_the_last_attempt_is_the_outcome(client, auth, project_role, report_now, seed_run):
    """Same run: failed then passed is a pass; passed then failed is a failure (highest row id wins)."""
    project_role()
    seed_run(at(9, 30), results=(("a", "passed", 1), ("b", "passed", 1)))
    seed_run(at(10, 2), results=(("a", "failed", 1), ("a", "passed", 1), ("b", "passed", 1), ("b", "failed", 1, "Boom: b")))
    r = regressions(client, auth)
    assert [i["name"] for i in r["newly_failing"]["items"]] == ["b"]
    assert r["newly_failing"]["items"][0]["headline"] == "Boom: b"
    assert [i["name"] for i in r["longest_failing"]["items"]] == ["b"]


def test_a_skipped_last_row_leaves_the_failed_attempt_as_the_outcome(client, auth, project_role, report_now, seed_run):
    """Failed, then skipped, in one run: skipped rows are no outcome, so the failed row is."""
    project_role()
    seed_run(at(9, 30), results=(("c", "passed", 1),))
    seed_run(at(10, 2), results=(("c", "failed", 1, "Boom: c"), ("c", "skipped", 0)))
    r = regressions(client, auth)
    assert [(i["name"], i["failures"], i["headline"]) for i in r["newly_failing"]["items"]] == [("c", 1, "Boom: c")]
    assert r["flakiness"][1]["flips"] == 1


def _every_outcome(db, ids, keys, by_id):
    """The definition, row by row: every test's last non-skipped attempt in every run, each with its headline."""
    from src.ingestion.analytics.report_streaks import Outcome
    from src.ingestion.analytics.signature import headline
    from src.ingestion.models import RunResult
    last = {}
    for row in db.query(RunResult).filter(RunResult.run_id.in_(ids), RunResult.test_key.in_(keys),
                                          RunResult.status != "skipped").order_by(RunResult.id):
        last[(row.run_id, row.test_key)] = row
    out = []
    for (run_id, key), row in last.items():
        passed = row.status == "passed"
        run = by_id[run_id]
        out.append(Outcome(key, run.branch, run_id, run.started_at, passed, None if passed else headline(row.message)))
    return out


@pytest.mark.parametrize("seed", range(6))
def test_the_section_equals_the_one_over_every_outcome(client, auth, project_role, report_now, seed_run, monkeypatch,
                                                       seed):
    """_outcomes fetches only the outcomes next to a failure; on random histories with retries, skips, absent tests
    and a null branch the section must equal the one built from every outcome."""
    import random
    from datetime import timedelta
    from src.ingestion.service import report_service
    project_role()
    rng = random.Random(seed)
    for _ in range(30):
        started = at(9, 24) + timedelta(minutes=rng.randrange(14 * 24 * 60))
        results = []
        for name in ("t0", "t1", "t2", "t3", "t4", "t5"):
            for _ in range(rng.choice((0, 1, 1, 1, 1, 2))):  # absent, once, or a retry
                status = rng.choices(("passed", "failed", "errored", "skipped"), (60, 20, 5, 15))[0]
                results.append((name, status, 1, f"E{rng.randint(1, 3)}: {name}\nat line {rng.randint(1, 9)}"))
        seed_run(started, branch=rng.choice(("main", "main", "dev", None)), results=tuple(results) or (("t0", "passed", 1),))
    for body in ({}, {"branch": "main"}, {"tz": "Europe/Lisbon"}):
        reshaped = regressions(client, auth, **body)
        with monkeypatch.context() as patch:
            patch.setattr(report_service, "_outcomes", _every_outcome)
            assert regressions(client, auth, **body) == reshaped
