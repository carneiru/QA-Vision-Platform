"""Flaky-test ranking over per-test totals. Pure: the database computes the totals.

`same_commit` (confirmed): the test both passed and failed for one (commit, environment).
`flips` (suspected): its outcome changed between consecutive executions on a branch often enough.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from src.ingestion.analytics.trends import as_utc

MAX_COMMITS = 5


@dataclass(frozen=True)
class FlipCount:
    test_key: str
    runs: int    # non-skipped executions in the window
    flips: int   # outcome changes between consecutive executions, per branch, summed
    pairs: int   # consecutive pairs, per branch, summed


@dataclass(frozen=True)
class MixedCommit:
    test_key: str
    commit_sha: str
    environment: Optional[str]
    latest: datetime


@dataclass(frozen=True)
class LatestExecution:
    test_key: str
    suite: str
    class_name: str
    name: str
    status: str
    started_at: datetime


def rank_flaky(
    flips: Iterable[FlipCount],
    mixed: Iterable[MixedCommit],
    latest: Dict[str, LatestExecution],
    *,
    min_runs: int,
    min_flip_rate: float,
    limit: int = 100,
) -> List[dict]:
    counts = {count.test_key: count for count in flips}
    commits_by_test: Dict[str, List[MixedCommit]] = defaultdict(list)
    for commit in mixed:
        commits_by_test[commit.test_key].append(commit)

    items = []
    for key, last in latest.items():
        count = counts.get(key)
        base = {
            "test_key": key,
            "suite": last.suite,
            "class_name": last.class_name,
            "name": last.name,
            "runs": count.runs if count else 0,
            "last_status": last.status,
            "last_seen": as_utc(last.started_at),
        }
        if key in commits_by_test:
            newest = sorted(commits_by_test[key], key=lambda c: (as_utc(c.latest), c.commit_sha), reverse=True)
            items.append({
                **base, "reason": "same_commit", "flips": None, "flip_rate": None,
                "commits": [{"commit_sha": c.commit_sha, "environment": c.environment} for c in newest[:MAX_COMMITS]],
            })
        elif (count and count.runs >= min_runs and count.pairs > 0 and count.flips > 0
              and count.flips / count.pairs >= min_flip_rate):
            items.append({
                **base, "reason": "flips", "commits": [], "flips": count.flips,
                "flip_rate": round(count.flips / count.pairs, 4),
            })

    items.sort(key=lambda item: (
        item["reason"] != "same_commit",
        -(item["flip_rate"] or 0.0),
        -item["last_seen"].timestamp(),
        item["test_key"],
    ))
    return items[:limit]
