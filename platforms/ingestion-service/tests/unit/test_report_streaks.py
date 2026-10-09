"""Outcome sequences per (test, branch) (spec: Section regressions; plan Ruling 9 for list orders)."""
from datetime import datetime, timedelta, timezone

from src.ingestion.analytics.report_streaks import Outcome, build_sequences, classify_streaks, flips_by_bucket

PREVIOUS_START = datetime(2026, 9, 24, tzinfo=timezone.utc)
PERIOD_START = datetime(2026, 10, 1, tzinfo=timezone.utc)
DAY = 86_400_000


def o(test, day, passed, run=None, branch="main", month=10, headline=None):
    started = datetime(2026, month, day, 10, tzinfo=timezone.utc)
    return Outcome(test, branch, run or month * 100 + day, started, passed, None if passed else (headline or f"{test} broke"))


def classify(*outcomes):
    return classify_streaks(build_sequences(outcomes), PERIOD_START, PREVIOUS_START)


def test_newly_failing_after_a_pass_in_the_previous_period():
    out = classify(o("t1", 25, True, month=9), o("t1", 2, False), o("t1", 3, False, headline="latest"))
    (item,) = out["newly_failing"]
    assert item["failing_since"] == datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
    assert item["last_passed_at"] == datetime(2026, 9, 25, 10, tzinfo=timezone.utc)
    assert (item["failures"], item["headline"], item["branch"]) == (2, "latest", "main")
    assert out["longest_failing"][0]["failing_since_bounded"] is False


def test_a_streak_that_began_before_the_period_is_not_new():
    out = classify(o("t1", 24, True, month=9), o("t1", 26, False, month=9), o("t1", 2, False))
    assert out["newly_failing"] == []
    assert out["longest_failing"][0]["failing_since"] == datetime(2026, 9, 26, 10, tzinfo=timezone.utc)


def test_a_streak_cut_off_by_the_look_back_is_bounded():
    out = classify(o("t3", 25, False, month=9), o("t3", 2, False), o("t3", 3, False))
    (item,) = out["longest_failing"]
    assert item["failing_since"] == PREVIOUS_START and item["failing_since_bounded"] is True
    assert item["consecutive_failures"] == 3 and out["newly_failing"] == []


def test_fixed_and_time_to_fix():
    out = classify(o("t2", 24, True, month=9), o("t2", 25, False, month=9), o("t2", 2, True),
                   o("t5", 2, False), o("t5", 4, True))
    fixed = {f["test_key"]: f for f in out["fixed"]}
    assert fixed["t2"]["time_to_fix_ms"] == 7 * DAY and fixed["t2"]["failing_since_bounded"] is False
    assert fixed["t5"]["time_to_fix_ms"] == 2 * DAY and fixed["t5"]["failing_since_bounded"] is True
    assert [f["test_key"] for f in out["fixed"]] == ["t5", "t2"]          # newest fix first
    assert out["time_to_fix"] == {"fixes": 2, "mean_ms": int(4.5 * DAY), "median_ms": int(4.5 * DAY),
                                  "p90_ms": int(6.5 * DAY), "bounded": 1}


def test_every_fix_inside_the_period_counts_toward_time_to_fix():
    out = classify(o("t1", 1, False), o("t1", 2, True), o("t1", 3, False), o("t1", 5, True))
    assert out["time_to_fix"]["fixes"] == 2
    assert [f["fixed_at"].day for f in out["fixed"]] == [5]               # only the current passing streak is "fixed"


def test_no_fixes_is_all_null():
    assert classify(o("t1", 2, True))["time_to_fix"] == {"fixes": 0, "mean_ms": None, "median_ms": None, "p90_ms": None, "bounded": 0}


def test_branches_are_separate_stories():
    out = classify(o("t1", 1, True, branch="main"), o("t1", 2, False, branch="main"), o("t1", 3, True, branch="dev"))
    assert [(i["test_key"], i["branch"]) for i in out["newly_failing"]] == [("t1", "main")]


def test_list_orders():
    out = classify(o("a", 1, True), o("a", 3, False), o("b", 1, True), o("b", 2, False),
                   o("c", 25, False, month=9), o("c", 2, False))
    assert [i["test_key"] for i in out["newly_failing"]] == ["a", "b"]         # newest first
    assert [i["test_key"] for i in out["longest_failing"]] == ["c", "b", "a"]  # oldest first


def test_flips_land_in_the_later_outcomes_bucket():
    seqs = build_sequences([o("t1", 25, True, month=9), o("t1", 2, False), o("t1", 4, True), o("t2", 4, True), o("t2", 5, True)])
    flips, flaky = flips_by_bucket(seqs, PERIOD_START, lambda moment: moment.day - 1, 7)
    assert flips == [0, 1, 0, 1, 0, 0, 0]
    assert flaky[1] == {"t1"} and flaky[3] == {"t1"} and flaky[4] == set()


def test_flips_per_test_are_summed_over_branches():
    from src.ingestion.analytics.report_streaks import count_flips
    seqs = build_sequences([o("t1", 1, True), o("t1", 2, False), o("t1", 3, True),
                            o("t1", 1, True, branch="dev"), o("t1", 2, False, branch="dev"), o("t2", 1, True)])
    assert count_flips(seqs) == {"t1": 3, "t2": 0}
