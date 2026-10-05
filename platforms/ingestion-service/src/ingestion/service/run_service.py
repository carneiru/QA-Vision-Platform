from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.ingestion.analytics.signature import headline, signature
from src.ingestion.models import Run, RunChangedFile, RunComponent, RunResult
from src.ingestion.service.analytics_service import _escape_like


@dataclass(frozen=True)
class RunFilters:
    branch: Optional[str] = None
    # failing: at least one failed or errored result; passing: none
    status: Optional[Literal["failing", "passing"]] = None
    environment: Optional[str] = None
    ci_provider: Optional[str] = None
    commit: Optional[str] = None  # hex prefix, any case
    pr: Optional[int] = None
    author: Optional[str] = None  # substring, case-insensitive
    since: Optional[datetime] = None  # started_at >= since
    until: Optional[datetime] = None  # started_at < until


def list_runs(db: Session, project_id: int, limit: int, offset: int, filters: RunFilters = RunFilters()) -> list[Run]:
    query = db.query(Run).filter(Run.project_id == project_id)
    f = filters
    if f.branch is not None:
        query = query.filter(Run.branch == f.branch)
    if f.status == "failing":
        query = query.filter((Run.failed + Run.errored) > 0)
    elif f.status == "passing":
        query = query.filter(Run.failed == 0, Run.errored == 0)
    if f.environment is not None:
        query = query.filter(Run.environment == f.environment)
    if f.ci_provider is not None:
        query = query.filter(Run.ci_provider == f.ci_provider)
    if f.commit is not None:
        query = query.filter(func.lower(Run.commit_sha).like(f"{f.commit.lower()}%"))
    if f.pr is not None:
        query = query.filter(Run.pr_number == f.pr)
    if f.author is not None:
        query = query.filter(Run.commit_author.ilike(f"%{_escape_like(f.author)}%", escape="\\"))
    if f.since is not None:
        query = query.filter(Run.started_at >= f.since)
    if f.until is not None:
        query = query.filter(Run.started_at < f.until)
    return query.order_by(Run.created_at.desc(), Run.id.desc()).offset(offset).limit(limit).all()


def get_run(db: Session, run_id: int) -> Optional[Run]:
    return db.get(Run, run_id)


def list_results(db: Session, run_id: int, status: Optional[str]) -> list[RunResult]:
    query = db.query(RunResult).filter(RunResult.run_id == run_id)
    if status is not None:
        query = query.filter(RunResult.status == status)
    return query.order_by(RunResult.id).all()


MAX_GROUP_TESTS = 100


def failure_groups(db: Session, run_id: int) -> dict:
    """The run's failed and errored tests grouped by cause, biggest group first."""
    rows = (
        db.query(RunResult.id, RunResult.test_key, RunResult.suite, RunResult.class_name, RunResult.name,
                 RunResult.status, RunResult.message)
        .filter(RunResult.run_id == run_id, RunResult.status.in_(("failed", "errored")))
        .order_by(RunResult.id).all()
    )
    groups: dict = {}
    for r in rows:
        key = signature(r.message)
        g = groups.get(key)
        if g is None:
            g = groups[key] = {"signature": key, "headline": headline(r.message), "count": 0, "failed": 0,
                               "errored": 0, "tests": [], "first": r.id}
        g["count"] += 1
        g[r.status] += 1
        if len(g["tests"]) < MAX_GROUP_TESTS:
            g["tests"].append({"id": r.id, "test_key": r.test_key, "suite": r.suite, "class_name": r.class_name,
                               "name": r.name, "status": r.status})
    ordered = sorted(groups.values(), key=lambda g: (-g["count"], g["signature"] == "none", g["first"]))
    for g in ordered:
        del g["first"]
    return {"total": len(rows), "groups": ordered}


def list_changes(db: Session, run_id: int) -> list[RunChangedFile]:
    return db.query(RunChangedFile).filter(RunChangedFile.run_id == run_id).order_by(RunChangedFile.id).all()


def list_components(db: Session, run_id: int) -> list[RunComponent]:
    return db.query(RunComponent).filter(RunComponent.run_id == run_id).order_by(RunComponent.id).all()
