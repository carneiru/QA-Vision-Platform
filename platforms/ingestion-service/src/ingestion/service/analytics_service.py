"""Database queries for the analytics endpoints. Counting stays in SQL; the ranking and day
grouping live in src/ingestion/analytics."""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.ingestion.analytics.flaky import LatestExecution
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
