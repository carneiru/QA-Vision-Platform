from typing import Optional

from sqlalchemy.orm import Session

from src.ingestion.models import Run, RunResult


def list_runs(db: Session, project_id: int, limit: int, offset: int, branch: Optional[str]) -> list[Run]:
    query = db.query(Run).filter(Run.project_id == project_id)
    if branch is not None:
        query = query.filter(Run.branch == branch)
    return query.order_by(Run.created_at.desc(), Run.id.desc()).offset(offset).limit(limit).all()


def get_run(db: Session, run_id: int) -> Optional[Run]:
    return db.get(Run, run_id)


def list_results(db: Session, run_id: int, status: Optional[str]) -> list[RunResult]:
    query = db.query(RunResult).filter(RunResult.run_id == run_id)
    if status is not None:
        query = query.filter(RunResult.status == status)
    return query.order_by(RunResult.id).all()
