"""Regressions and stability (spec: Section regressions). Pure: the service hands over each test's last-attempt,
non-skipped outcomes per run, only those next to a failure; the story of a test is told per branch."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from src.ingestion.analytics.report_stats import mean, percentile

SequenceKey = Tuple[str, Optional[str]]


@dataclass(frozen=True)
class Outcome:
    test_key: str
    branch: Optional[str]
    run_id: int
    started_at: datetime
    passed: bool
    headline: Optional[str]  # only on the last failing outcome of a sequence; None elsewhere


def build_sequences(outcomes: Iterable[Outcome]) -> Dict[SequenceKey, List[Outcome]]:
    sequences: Dict[SequenceKey, List[Outcome]] = defaultdict(list)
    for outcome in outcomes:
        sequences[(outcome.test_key, outcome.branch)].append(outcome)
    for sequence in sequences.values():
        sequence.sort(key=lambda x: (x.started_at, x.run_id))
    return dict(sequences)


def _ms(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() * 1000)


def classify_streaks(sequences: Dict[SequenceKey, List[Outcome]], period_start: datetime,
                     previous_start: datetime) -> dict:
    newly, fixed, longest, fixes = [], [], [], []
    for (key, branch), seq in sequences.items():
        last = seq[-1]
        streak = len(seq) - 1  # index where the current streak starts
        while streak > 0 and seq[streak - 1].passed == last.passed:
            streak -= 1
        start, before = seq[streak], (seq[streak - 1] if streak > 0 else None)
        base = {"test_key": key, "branch": branch}
        if not last.passed:
            cut = before is None  # the streak reaches back past the look-back: its start is unknown
            longest.append({**base, "failing_since": previous_start if cut else start.started_at,
                            "failing_since_bounded": cut, "consecutive_failures": len(seq) - streak,
                            "last_run_id": last.run_id, "headline": last.headline})
            if before is not None and start.started_at >= period_start:
                newly.append({**base, "failing_since": start.started_at, "failing_since_run_id": start.run_id,
                              "last_passed_at": before.started_at, "last_passed_run_id": before.run_id,
                              "failures": len(seq) - streak, "headline": last.headline})
        # Every failing streak that ended inside the period: a pass after one or more failures
        j = 0
        while j < len(seq):
            if seq[j].passed:
                j += 1
                continue
            k = j
            while k < len(seq) and not seq[k].passed:
                k += 1
            if k < len(seq) and seq[k].started_at >= period_start:
                cut = j == 0
                took = _ms(seq[j].started_at, seq[k].started_at)
                fixes.append((took, cut))
                if last.passed and k == streak:
                    fixed.append({**base, "fixed_at": seq[k].started_at, "fixed_run_id": seq[k].run_id,
                                  "failing_since": seq[j].started_at, "failing_since_bounded": cut,
                                  "time_to_fix_ms": took})
            j = k
    tie = lambda item: (item["test_key"], item["branch"] or "")  # noqa: E731
    newly.sort(key=lambda i: (-i["failing_since"].timestamp(), *tie(i)))
    fixed.sort(key=lambda i: (-i["fixed_at"].timestamp(), *tie(i)))
    longest.sort(key=lambda i: (i["failing_since"], -i["consecutive_failures"], *tie(i)))
    took = [ms for ms, _ in fixes]
    return {
        "newly_failing": newly, "fixed": fixed, "longest_failing": longest,
        "time_to_fix": {"fixes": len(took), "mean_ms": mean(took), "median_ms": percentile(took, 0.5),
                        "p90_ms": percentile(took, 0.9), "bounded": sum(1 for _, cut in fixes if cut)},
    }


def flips_by_bucket(sequences: Dict[SequenceKey, List[Outcome]], period_start: datetime,
                    bucket_of: Callable[[datetime], Optional[int]], bucket_count: int) -> Tuple[List[int], List[Set[str]]]:
    """A flip is an outcome change between consecutive outcomes on one branch, counted in the bucket of the later
    outcome; a test with a flip in a bucket is flaky in that bucket ("Instability (flips)")."""
    flips = [0] * bucket_count
    flaky: List[Set[str]] = [set() for _ in range(bucket_count)]
    for (key, _), seq in sequences.items():
        for before, after in zip(seq, seq[1:]):
            if after.started_at < period_start or before.passed == after.passed:
                continue
            index = bucket_of(after.started_at)
            if index is None:
                continue
            flips[index] += 1
            flaky[index].add(key)
    return flips, flaky
