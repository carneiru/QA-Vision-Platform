"""Database queries for the analytics endpoints. Counting stays in SQL; the ranking and day
grouping live in src/ingestion/analytics."""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.ingestion.analytics.flaky import FlipCount, LatestExecution, MixedCommit
from src.ingestion.analytics.trends import RunRow, as_utc, pass_rate
from src.ingestion.models import Run, RunResult


def _count(*statuses: str):
    return func.sum(case((RunResult.status.in_(statuses), 1), else_=0))


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def window_filters(project_id: int, since: datetime, branch: Optional[str] = None) -> list:
    filters = [Run.project_id == project_id, Run.started_at >= since]
    if branch is not None:
        filters.append(Run.branch == branch)
    return filters


def trend_rows(db: Session, project_id: int, since: datetime, branch: Optional[str],
               environment: Optional[str]) -> List[RunRow]:
    query = db.query(Run.started_at, Run.total, Run.passed, Run.failed, Run.errored, Run.skipped,
                     Run.duration_ms).filter(*window_filters(project_id, since, branch))
    if environment is not None:
        query = query.filter(Run.environment == environment)
    return [RunRow(*row) for row in query.all()]


def latest_executions(db: Session, filters: list, keys_clause) -> Dict[str, LatestExecution]:
    """The newest execution (started_at, then run id) of each test matching the filters."""
    ranked = (
        select(
            RunResult.test_key, RunResult.suite, RunResult.class_name, RunResult.name, RunResult.status,
            Run.started_at,
            func.row_number().over(
                partition_by=RunResult.test_key, order_by=(Run.started_at.desc(), Run.id.desc())
            ).label("position"),
        )
        .join(Run, Run.id == RunResult.run_id)
        .where(*filters, keys_clause)
    ).subquery()
    rows = db.execute(select(ranked).where(ranked.c.position == 1)).all()
    return {
        row.test_key: LatestExecution(row.test_key, row.suite, row.class_name, row.name, row.status,
                                      as_utc(row.started_at))
        for row in rows
    }


def list_tests(db: Session, project_id: int, since: datetime, *, sort: str, search: Optional[str],
               limit: int, offset: int) -> List[dict]:
    failures = _count("failed", "errored")
    average = func.avg(RunResult.duration_ms)
    name = func.max(RunResult.name)
    filters = window_filters(project_id, since)
    query = (
        db.query(
            RunResult.test_key, func.max(RunResult.suite), func.max(RunResult.class_name), name,
            func.count(RunResult.id), _count("passed"), _count("failed"), _count("errored"), _count("skipped"),
            average,
        )
        .join(Run, Run.id == RunResult.run_id)
        .filter(*filters)
        .group_by(RunResult.test_key)
    )
    if search:
        query = query.filter(RunResult.name.ilike(f"%{_escape_like(search)}%", escape="\\"))
    order = {"failures": failures.desc(), "duration": average.desc(), "name": name.asc()}[sort]
    rows = query.order_by(order, RunResult.test_key).offset(offset).limit(limit).all()

    latest = latest_executions(db, filters, RunResult.test_key.in_([row[0] for row in rows])) if rows else {}
    out = []
    for key, suite, class_name, test_name, runs, passed, failed, errored, skipped, avg in rows:
        last = latest[key]
        out.append({
            "test_key": key, "suite": suite, "class_name": class_name, "name": test_name,
            "runs": runs, "passed": int(passed), "failed": int(failed), "errored": int(errored),
            "skipped": int(skipped), "pass_rate": pass_rate(int(passed), runs, int(skipped)),
            "avg_duration_ms": round(float(avg)) if avg is not None else None,
            "last_status": last.status, "last_seen": last.started_at,
        })
    return out


MESSAGE_EXCERPT = 500


def test_seen(db: Session, project_id: int, test_key: str) -> bool:
    return db.query(RunResult.id).join(Run, Run.id == RunResult.run_id).filter(
        Run.project_id == project_id, RunResult.test_key == test_key
    ).first() is not None


test_seen.__test__ = False  # not a pytest test, despite the name


def test_history(db: Session, project_id: int, test_key: str, since: datetime, branch: Optional[str],
                 limit: int) -> dict:
    filters = window_filters(project_id, since, branch) + [RunResult.test_key == test_key]
    base = db.query(RunResult).join(Run, Run.id == RunResult.run_id).filter(*filters)
    rows = base.with_entities(
        Run.id, Run.started_at, Run.branch, Run.commit_sha, Run.environment, RunResult.status,
        RunResult.duration_ms, RunResult.message, RunResult.suite, RunResult.class_name, RunResult.name,
    ).order_by(Run.started_at.desc(), Run.id.desc()).limit(limit).all()
    runs, passed, failed, errored, skipped, avg = base.with_entities(
        func.count(RunResult.id), _count("passed"), _count("failed"), _count("errored"), _count("skipped"),
        func.avg(RunResult.duration_ms),
    ).one()

    if rows:
        identity = rows[0][8:11]
    else:  # known test, nothing in the window: identity from its latest execution ever
        identity = db.query(RunResult.suite, RunResult.class_name, RunResult.name).join(
            Run, Run.id == RunResult.run_id
        ).filter(Run.project_id == project_id, RunResult.test_key == test_key).order_by(
            Run.started_at.desc(), Run.id.desc()
        ).first()
    passed, failed, errored, skipped = (int(v or 0) for v in (passed, failed, errored, skipped))
    return {
        "test_key": test_key, "suite": identity[0], "class_name": identity[1], "name": identity[2],
        "summary": {
            "runs": runs, "passed": passed, "failed": failed, "errored": errored, "skipped": skipped,
            "pass_rate": pass_rate(passed, runs, skipped),
            "avg_duration_ms": round(float(avg)) if avg is not None else None,
        },
        "executions": [
            {"run_id": run_id, "started_at": as_utc(started_at), "branch": run_branch, "commit_sha": commit_sha,
             "environment": environment, "status": status, "duration_ms": duration_ms,
             "message": message[:MESSAGE_EXCERPT] if message is not None else None}
            for run_id, started_at, run_branch, commit_sha, environment, status, duration_ms, message, *_ in rows
        ],
    }


test_history.__test__ = False  # not a pytest test, despite the name


def flaky_inputs(db: Session, project_id: int, since: datetime, branch: Optional[str]):
    """Per-test flip totals, mixed (commit, environment) groups, and latest executions, for the
    tests with at least one failure in the window. All counting happens in the database."""
    filters = window_filters(project_id, since, branch)
    candidates = select(RunResult.test_key).join(Run, Run.id == RunResult.run_id).where(
        *filters, RunResult.status.in_(("failed", "errored"))
    ).distinct()
    executions = filters + [RunResult.status != "skipped", RunResult.test_key.in_(candidates)]

    outcome = case((RunResult.status == "passed", "pass"), else_="fail")
    sequence = (
        select(
            RunResult.test_key.label("test_key"),
            outcome.label("outcome"),
            func.lag(outcome).over(
                partition_by=(RunResult.test_key, Run.branch), order_by=(Run.started_at, Run.id)
            ).label("previous"),
        )
        .join(Run, Run.id == RunResult.run_id)
        .where(*executions)
    ).subquery()
    has_previous = sequence.c.previous.is_not(None)
    flip_rows = db.execute(
        select(
            sequence.c.test_key,
            func.count(),
            func.sum(case(((has_previous & (sequence.c.previous != sequence.c.outcome)), 1), else_=0)),
            func.sum(case((has_previous, 1), else_=0)),
        ).group_by(sequence.c.test_key)
    ).all()
    flips = [FlipCount(key, runs, int(flipped or 0), int(pairs or 0)) for key, runs, flipped, pairs in flip_rows]

    mixed_rows = db.execute(
        select(RunResult.test_key, Run.commit_sha, Run.environment, func.max(Run.started_at))
        .join(Run, Run.id == RunResult.run_id)
        .where(*executions, Run.commit_sha.is_not(None))
        .group_by(RunResult.test_key, Run.commit_sha, Run.environment)
        .having((_count("passed") > 0) & (_count("failed", "errored") > 0))
    ).all()
    mixed = [MixedCommit(key, sha, environment, as_utc(latest)) for key, sha, environment, latest in mixed_rows]

    latest = latest_executions(db, filters + [RunResult.status != "skipped"], RunResult.test_key.in_(candidates))
    return flips, mixed, latest
