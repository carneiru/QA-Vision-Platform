from datetime import datetime, timedelta, timezone

from src.ingestion.analytics.flaky import FlipCount, LatestExecution, MixedCommit, rank_flaky

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def latest(key, status="failed", minutes=0, name=None):
    return LatestExecution(key, "s", "C", name or key, status, NOW - timedelta(minutes=minutes))


def rank(flips=(), mixed=(), rows=(), min_runs=5, min_flip_rate=0.3, limit=100):
    return rank_flaky(flips, mixed, {r.test_key: r for r in rows}, min_runs=min_runs,
                      min_flip_rate=min_flip_rate, limit=limit)


def test_a_mixed_commit_is_confirmed():
    items = rank(flips=[FlipCount("k", 2, 1, 1)], mixed=[MixedCommit("k", "c1", None, NOW)], rows=[latest("k")])
    assert items == [{
        "test_key": "k", "suite": "s", "class_name": "C", "name": "k", "reason": "same_commit",
        "commits": [{"commit_sha": "c1", "environment": None}], "flips": None, "flip_rate": None,
        "runs": 2, "last_status": "failed", "last_seen": NOW,
    }]


def test_flips_at_or_above_the_rate_are_suspected():
    rows, flips = [latest("k", status="passed")], [FlipCount("k", 6, 2, 5)]  # 2 of 5 pairs = 0.4
    item = rank(flips=flips, rows=rows, min_flip_rate=0.4)[0]
    assert (item["reason"], item["flips"], item["flip_rate"], item["commits"], item["runs"]) == ("flips", 2, 0.4, [], 6)
    assert rank(flips=flips, rows=rows, min_flip_rate=0.5) == []


def test_too_few_runs_or_no_pairs_are_not_suspected():
    assert rank(flips=[FlipCount("k", 4, 3, 3)], rows=[latest("k")]) == []
    assert rank(flips=[FlipCount("k", 5, 0, 0)], rows=[latest("k")]) == []
    assert rank(rows=[latest("k")]) == []


def test_a_confirmed_test_is_not_listed_again_under_flips():
    items = rank(flips=[FlipCount("k", 9, 8, 8)], mixed=[MixedCommit("k", "c1", "py39", NOW)], rows=[latest("k")])
    assert [(i["test_key"], i["reason"]) for i in items] == [("k", "same_commit")]
    assert items[0]["commits"] == [{"commit_sha": "c1", "environment": "py39"}]


def test_order_confirmed_then_flip_rate_then_last_seen():
    rows = [latest("k3", minutes=60), latest("k1", minutes=10), latest("k2", minutes=1), latest("k4", minutes=5)]
    flips = [FlipCount("k1", 5, 4, 4), FlipCount("k2", 6, 2, 5), FlipCount("k4", 5, 4, 4)]
    mixed = [MixedCommit("k3", "c1", None, NOW - timedelta(minutes=60))]
    assert [i["test_key"] for i in rank(flips=flips, mixed=mixed, rows=rows)] == ["k3", "k4", "k1", "k2"]


def test_at_most_five_commits_most_recent_first():
    mixed = [MixedCommit("k", f"c{i}", None, NOW - timedelta(minutes=i)) for i in range(6)]
    commits = rank(mixed=mixed, rows=[latest("k")])[0]["commits"]
    assert [c["commit_sha"] for c in commits] == ["c0", "c1", "c2", "c3", "c4"]


def test_identity_comes_from_the_latest_execution():
    item = rank(mixed=[MixedCommit("k", "c1", None, NOW)], rows=[latest("k", name="renamed")])[0]
    assert item["name"] == "renamed"


def test_at_most_limit_items():
    rows = [latest(f"k{i:03d}") for i in range(150)]
    flips = [FlipCount(f"k{i:03d}", 5, 4, 4) for i in range(150)]
    assert len(rank(flips=flips, rows=rows)) == 100


def test_a_zero_flip_rate_threshold_never_lists_tests_that_did_not_flip():
    assert rank(flips=[FlipCount("k", 9, 0, 8)], rows=[latest("k")], min_flip_rate=0) == []
