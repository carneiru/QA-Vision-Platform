"""Daily flaky rollups: compute one day exactly once, recombine windows from
the daily rows. The recombination reproduces the live scan's numbers —
equivalence is pinned by tests/unit/test_flaky_rollup.py."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.ingestion.analytics.flaky import FlipCount, LatestExecution, MixedCommit
from src.ingestion.analytics.trends import as_utc
from src.ingestion.models import Run, RunResult
from src.ingestion.models.flaky_rollup import FlakyDaily, FlakyRollupDay


def _day_bounds(day: date) -> Tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _outcome(status: str) -> str:
    return "pass" if status == "passed" else "fail"


def upsert_day(db: Session, project_id: int, day: date) -> None:
    """Recompute one project-day from the raw executions; idempotent."""
    start, end = _day_bounds(day)
    rows = db.execute(
        select(
            RunResult.test_key, RunResult.suite, RunResult.class_name, RunResult.name,
            RunResult.status, Run.branch, Run.commit_sha, Run.environment,
            Run.started_at, Run.id,
        )
        .join(Run, Run.id == RunResult.run_id)
        .where(
            Run.project_id == project_id,
            Run.started_at >= start,
            Run.started_at < end,
            RunResult.status != "skipped",
        )
        .order_by(Run.started_at, Run.id)
    ).all()

    db.execute(delete(FlakyDaily).where(FlakyDaily.project_id == project_id, FlakyDaily.day == day))
    db.execute(
        delete(FlakyRollupDay).where(
            FlakyRollupDay.project_id == project_id, FlakyRollupDay.day == day
        )
    )
    db.add(FlakyRollupDay(project_id=project_id, day=day))

    daily: Dict[tuple, dict] = {}
    for key, suite, class_name, name, status, branch, _sha, _env, started_at, _run_id in rows:
        outcome = _outcome(status)
        entry = daily.get((key, branch))
        if entry is None:
            daily[(key, branch)] = entry = {
                "suite": suite, "class_name": class_name, "name": name,
                "runs": 0, "flips": 0, "failures": 0,
                "first": outcome, "last_outcome": outcome, "last_status": status,
                "last_seen": started_at,
            }
        else:
            if outcome != entry["last_outcome"]:
                entry["flips"] += 1
        entry["runs"] += 1
        entry["failures"] += 1 if status in ("failed", "errored") else 0
        entry["last_outcome"] = outcome
        entry["last_status"] = status
        entry["last_seen"] = started_at
        entry["suite"], entry["class_name"], entry["name"] = suite, class_name, name

    for (key, branch), entry in daily.items():
        db.add(FlakyDaily(
            project_id=project_id, day=day, branch=branch, test_key=key,
            suite=entry["suite"], class_name=entry["class_name"], name=entry["name"],
            runs=entry["runs"], flips=entry["flips"], failures=entry["failures"],
            first_status=entry["first"], last_status=entry["last_status"],
            last_outcome=entry["last_outcome"], last_seen=entry["last_seen"],
        ))
    db.commit()


def has_rollups(db: Session, project_id: int) -> bool:
    return db.execute(
        select(FlakyDaily.id).where(FlakyDaily.project_id == project_id).limit(1)
    ).first() is not None


def rollup_inputs(
    db: Session, project_id: int, since_day: date, branch: Optional[str]
) -> Tuple[List[FlipCount], List[MixedCommit], Dict[str, LatestExecution]]:
    """The same three inputs flaky_inputs produces, from the daily rows."""
    daily_filters = [FlakyDaily.project_id == project_id, FlakyDaily.day >= since_day]
    if branch:
        daily_filters.append(FlakyDaily.branch == branch)

    day_rows = db.execute(
        select(
            FlakyDaily.test_key, FlakyDaily.branch, FlakyDaily.suite, FlakyDaily.class_name,
            FlakyDaily.name, FlakyDaily.runs, FlakyDaily.flips, FlakyDaily.failures,
            FlakyDaily.first_status, FlakyDaily.last_status, FlakyDaily.last_outcome,
            FlakyDaily.last_seen,
        ).where(*daily_filters).order_by(FlakyDaily.test_key, FlakyDaily.day)
    ).all()

    per_branch: Dict[tuple, list] = defaultdict(list)
    for row in day_rows:
        per_branch[(row.test_key, row.branch)].append(row)

    totals: Dict[str, dict] = defaultdict(lambda: {"runs": 0, "flips": 0, "pairs": 0, "failures": 0})
    latest_row: Dict[str, FlakyDaily] = {}
    for (key, _branch), rows in per_branch.items():
        branch_runs = sum(r.runs for r in rows)
        flips = sum(r.flips for r in rows)
        for previous, current in zip(rows, rows[1:]):  # day-boundary transitions
            if previous.last_outcome != current.first_status:
                flips += 1
        bucket = totals[key]
        bucket["runs"] += branch_runs
        bucket["flips"] += flips
        bucket["pairs"] += max(0, branch_runs - 1)
        bucket["failures"] += sum(r.failures for r in rows)
        newest = rows[-1]
        held = latest_row.get(key)
        if held is None or as_utc(newest.last_seen) > as_utc(held.last_seen):
            latest_row[key] = newest

    candidates = {key for key, bucket in totals.items() if bucket["failures"] > 0}
    flips_out = [
        FlipCount(key, bucket["runs"], bucket["flips"], bucket["pairs"])
        for key, bucket in totals.items() if key in candidates
    ]
    latest = {
        key: LatestExecution(
            key, row.suite, row.class_name, row.name, row.last_status, as_utc(row.last_seen)
        )
        for key, row in latest_row.items() if key in candidates
    }

    # Mixed-commit (confirmed) detection stays on the live pass: it is driven
    # by the window's failures through the (test_key, run_id) index and does
    # not need daily rows. Imported lazily: analytics_service imports this
    # module's inputs' types from flaky.py, keeping the cycle out.
    from src.ingestion.service.analytics_service import mixed_commits

    since_ts = datetime.combine(since_day, time.min, tzinfo=timezone.utc)
    mixed = [m for m in mixed_commits(db, project_id, since_ts, branch) if m.test_key in candidates]
    return flips_out, mixed, latest
