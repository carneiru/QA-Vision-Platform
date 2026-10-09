"""Failure causes over a period (spec: Section failure_causes): the run view's signature groups
(analytics/signature.py, unchanged) extended from one run to a period, against the previous period. Pure."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, Optional

from src.ingestion.analytics.report_period import iso
from src.ingestion.analytics.signature import NONE

MAX_GROUPS = 50
MAX_TOP_TESTS = 10
MAX_RESOLVED = 20


@dataclass(frozen=True)
class Occurrence:
    """One failing result (failed or errored) of an in-scope run."""
    signature: str
    headline: Optional[str]
    test_key: str
    suite: str
    class_name: str
    name: str
    status: str
    run_id: int
    started_at: datetime
    current: bool              # in the period; False: in the previous period
    quarantined: bool          # the test is muted: shown and counted, flagged
    bucket: Optional[int]      # index into the period's buckets; None in the previous period


def group_causes(occurrences: Iterable[Occurrence], bucket_count: int) -> dict:
    ordered = sorted(occurrences, key=lambda o: (o.started_at, o.run_id))
    first: Dict[str, Occurrence] = {}
    previous: Dict[str, int] = defaultdict(int)
    previous_last: Dict[str, datetime] = {}
    previous_headline: Dict[str, Optional[str]] = {}
    groups: Dict[str, dict] = {}
    for o in ordered:
        first.setdefault(o.signature, o)
        if not o.current:
            previous[o.signature] += 1
            previous_last[o.signature] = o.started_at
            previous_headline.setdefault(o.signature, o.headline)
            continue
        g = groups.get(o.signature)
        if g is None:
            g = groups[o.signature] = {
                "signature": o.signature, "headline": o.headline, "occurrences": 0, "failed": 0, "errored": 0,
                "quarantined": 0, "buckets": [0] * bucket_count, "_tests": {}, "_runs": set(), "_last": o,
            }
        g["occurrences"] += 1
        g[o.status] += 1
        g["quarantined"] += int(o.quarantined)
        g["_runs"].add(o.run_id)
        g["_last"] = o
        if o.bucket is not None:
            g["buckets"][o.bucket] += 1
        test = g["_tests"].setdefault(o.test_key, {"test_key": o.test_key, "suite": o.suite, "class_name": o.class_name,
                                                   "name": o.name, "occurrences": 0, "last_run_id": o.run_id})
        test["occurrences"] += 1
        test["last_run_id"] = o.run_id

    rows = []
    for signature, g in groups.items():
        seen_first, last = first[signature], g.pop("_last")
        tests, runs = g.pop("_tests"), g.pop("_runs")
        g.update({
            "tests": len(tests), "runs": len(runs),
            "status": "recurring" if previous.get(signature) else "new",
            "previous_occurrences": previous.get(signature, 0),
            "first_seen": iso(seen_first.started_at), "first_seen_run_id": seen_first.run_id,
            "last_seen": iso(last.started_at), "last_seen_run_id": last.run_id,
            "top_tests": sorted(tests.values(), key=lambda t: (-t["occurrences"], t["test_key"]))[:MAX_TOP_TESTS],
        })
        rows.append((last.started_at, g))
    # Biggest first; ties to the newer last_seen, then the signature, with "none" last among equals
    rows.sort(key=lambda pair: (-pair[1]["occurrences"], -pair[0].timestamp(), pair[1]["signature"] == NONE,
                                pair[1]["signature"]))
    ordered_groups = [g for _, g in rows]
    kept, rest = ordered_groups[:MAX_GROUPS], ordered_groups[MAX_GROUPS:]
    resolved = sorted(
        ({"signature": s, "headline": previous_headline[s], "previous_occurrences": n, "last_seen": iso(previous_last[s])}
         for s, n in previous.items() if s not in groups),
        key=lambda r: (-r["previous_occurrences"], r["signature"]),
    )
    return {
        "failures": sum(g["occurrences"] for g in ordered_groups),
        "groups_total": len(ordered_groups),
        "groups": kept,
        "other": {"groups": len(rest), "occurrences": sum(g["occurrences"] for g in rest)},
        "resolved": resolved[:MAX_RESOLVED],
    }
