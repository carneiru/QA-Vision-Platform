"""Section failure_causes (spec: Section failure_causes (P2))."""
from datetime import datetime, timezone

import pytest

from src.ingestion.analytics.signature import signature
from src.ingestion.models import MutedTest
from conftest import post_report, report_key

TIMEOUT = "TimeoutError: locator('#pay') after {} ms"


def at(month, day):
    return datetime(2026, month, day, 10, tzinfo=timezone.utc)


@pytest.fixture
def seeded(project_role, report_now, seed_run):
    project_role()
    seed_run(at(9, 25), results=(("t1", "failed", 1, TIMEOUT.format(3000)), ("t5", "failed", 1, "Gone: old cause 1")))
    seed_run(at(10, 2), results=(("t1", "failed", 1, TIMEOUT.format(5000)), ("t2", "failed", 1, "AssertionError: expected 3 got 4"),
                                 ("t3", "errored", 1, None)))
    seed_run(at(10, 5), results=(("t1", "failed", 1, TIMEOUT.format(4000)), ("t2", "passed", 1)))


def causes(client, auth, **body):
    response = post_report(client, auth, sections=["failure_causes"], **body)
    assert response.status_code == 200, response.text
    return response.json()["failure_causes"]


def test_groups_new_recurring_resolved(client, auth, seeded):
    c = causes(client, auth)
    assert c["failures"] == 4 and c["groups_total"] == 3
    timeout, assertion, none = c["groups"]
    assert timeout["signature"] == signature(TIMEOUT.format(1)) and timeout["occurrences"] == 2
    assert (timeout["status"], timeout["previous_occurrences"], timeout["first_seen"]) == ("recurring", 1, "2026-09-25T10:00:00Z")
    assert (timeout["tests"], timeout["runs"]) == (1, 2)
    assert timeout["buckets"] == [0, 1, 0, 0, 1, 0, 0]
    assert timeout["top_tests"][0]["name"] == "t1" and timeout["top_tests"][0]["occurrences"] == 2
    assert assertion["status"] == "new" and assertion["headline"] == "AssertionError: expected 3 got 4"
    assert none["signature"] == "none" and none["errored"] == 1          # a tie with the assertion: none sorts last
    assert [r["headline"] for r in c["resolved"]] == ["Gone: old cause 1"]


def test_quarantined_occurrences_still_count(client, auth, seeded, db):
    db.add(MutedTest(project_id=1, test_key=report_key("t1"), muted_by_user_id=1))
    db.commit()
    timeout = causes(client, auth)["groups"][0]
    assert (timeout["occurrences"], timeout["quarantined"]) == (2, 2)


def test_filters_apply(client, auth, seeded):
    c = causes(client, auth, test_keys=[report_key("t2")])
    assert [g["headline"] for g in c["groups"]] == ["AssertionError: expected 3 got 4"] and c["resolved"] == []
    assert causes(client, auth, branch="dev") == {"failures": 0, "groups_total": 0, "groups": [],
                                                  "other": {"groups": 0, "occurrences": 0}, "resolved": []}


def test_previous_period_rows_never_reach_the_buckets(client, auth, project_role, report_now, seed_run):
    """Previous-period failures carry no bucket; passing rows never reach group_causes (no KeyError)."""
    project_role()
    seed_run(at(9, 24), results=(("t1", "failed", 1, "Old: boom"), ("t2", "passed", 1), ("t4", "skipped", 1)))
    seed_run(at(10, 7), results=(("t1", "failed", 1, "Old: boom"), ("t2", "passed", 1)))
    c = causes(client, auth, bucket="day")
    (group,) = c["groups"]
    assert group["occurrences"] == 1 and group["previous_occurrences"] == 1 and group["status"] == "recurring"
    assert group["buckets"] == [0, 0, 0, 0, 0, 0, 1] and sum(group["buckets"]) == group["occurrences"]
    assert c["resolved"] == []
