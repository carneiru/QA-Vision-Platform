"""Failure causes over a period (spec: Section failure_causes)."""
from datetime import datetime, timezone

from src.ingestion.analytics import report_causes
from src.ingestion.analytics.report_causes import Occurrence, group_causes


def occ(sig, *, day=2, test="t1", run=1, status="failed", current=True, quarantined=False, bucket=None, headline=None):
    started = datetime(2026, 10 if current else 9, day, 10, tzinfo=timezone.utc)
    return Occurrence(sig, headline or f"{sig} headline", f"key-{test}", "s", "C", test, status, run, started, current,
                      quarantined, bucket if bucket is not None else (day - 1 if current else None))


def test_new_recurring_and_resolved():
    out = group_causes([
        occ("aaa", current=False, day=25, run=1),
        occ("aaa", day=2, run=5), occ("aaa", day=3, run=6, test="t2"),
        occ("bbb", day=4, run=7, status="errored"),
        occ("gone", current=False, day=26, run=2),
    ], bucket_count=7)
    groups = {g["signature"]: g for g in out["groups"]}
    assert out["failures"] == 3 and out["groups_total"] == 2
    assert groups["aaa"]["status"] == "recurring" and groups["aaa"]["previous_occurrences"] == 1
    assert groups["aaa"]["first_seen"] == "2026-09-25T10:00:00Z" and groups["aaa"]["first_seen_run_id"] == 1
    assert groups["aaa"]["last_seen"] == "2026-10-03T10:00:00Z" and groups["aaa"]["last_seen_run_id"] == 6
    assert (groups["aaa"]["tests"], groups["aaa"]["runs"]) == (2, 2)
    assert groups["aaa"]["buckets"] == [0, 1, 1, 0, 0, 0, 0]
    assert groups["bbb"]["status"] == "new" and (groups["bbb"]["failed"], groups["bbb"]["errored"]) == (0, 1)
    assert out["resolved"] == [{"signature": "gone", "headline": "gone headline", "previous_occurrences": 1,
                                "last_seen": "2026-09-26T10:00:00Z"}]


def test_order_is_occurrences_then_newer_last_seen_then_signature_and_none_last():
    out = group_causes([
        occ("zzz", day=3, run=3), occ("none", day=3, run=3), occ("mmm", day=2, run=2),
        occ("big", day=1, run=1), occ("big", day=1, run=1),
    ], bucket_count=7)
    assert [g["signature"] for g in out["groups"]] == ["big", "zzz", "none", "mmm"]


def test_the_cap_and_other(monkeypatch):
    monkeypatch.setattr(report_causes, "MAX_GROUPS", 2)
    out = group_causes([occ("a"), occ("a"), occ("a"), occ("b"), occ("b"), occ("c"), occ("d")], bucket_count=7)
    assert [g["signature"] for g in out["groups"]] == ["a", "b"]
    assert out["other"] == {"groups": 2, "occurrences": 2}
    assert out["groups_total"] == 4 and out["failures"] == 7


def test_top_tests_and_quarantine():
    out = group_causes([occ("a", test="t1", run=1), occ("a", test="t2", run=1, quarantined=True), occ("a", test="t2", run=2, day=3)],
                       bucket_count=7)
    group = out["groups"][0]
    assert group["quarantined"] == 1
    assert [(t["name"], t["occurrences"], t["last_run_id"]) for t in group["top_tests"]] == [("t2", 2, 2), ("t1", 1, 1)]


def test_nothing_failed():
    assert group_causes([], bucket_count=7) == {"failures": 0, "groups_total": 0, "groups": [],
                                                "other": {"groups": 0, "occurrences": 0}, "resolved": []}
