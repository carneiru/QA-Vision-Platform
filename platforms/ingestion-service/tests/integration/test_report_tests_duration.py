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


def test_flips_over_a_long_pass_run_equal_the_full_sequence(client, auth, project_role, report_now, seed_run):
    """_outcomes drops the passes inside a pass run; the flips must still equal those over every outcome."""
    project_role()
    # F, P x4, F, P in the 7-day period: 3 flips over 6 pairs, whatever _outcomes drops
    statuses = ("failed", "passed", "passed", "passed", "passed", "failed", "passed")
    for day, status in enumerate(statuses, start=1):
        seed_run(at(10, day), results=(("t1", status, 1),))
    t = section(client, auth, "tests")
    row = dict(zip(t["columns"], t["rows"][0]))
    assert (row["flips"], row["pairs"], row["executions"]) == (3, 6, 7)
