"""Queries behind POST /analytics/duration-estimate. Two statements: the tests' executions in the window,
and the project's last runs for the wall-clock model. Percentiles and the fit are computed in Python
(src/ingestion/analytics/duration.py): at most 200 tests over 30 days is a bounded read."""
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.ingestion.analytics.duration import Execution, Model, combine, durations_for, fit_model
from src.ingestion.models import Run, RunResult
from src.ingestion.service.report_service import in_list

MODEL_RUNS = 20


def executions(db: Session, project_id: int, keys: Sequence[str], since: datetime) -> Dict[str, List[Execution]]:
    """Every non-skipped execution of these tests since `since`; the keys go to PostgreSQL as one array."""
    rows = db.execute(
        select(RunResult.test_key, RunResult.status, RunResult.duration_ms, Run.environment)
        .join(Run, Run.id == RunResult.run_id)
        .where(Run.project_id == project_id, Run.started_at >= since, in_list(db, RunResult.test_key, keys),
               RunResult.status != "skipped")
    ).all()
    found: Dict[str, List[Execution]] = defaultdict(list)
    for key, status, duration, environment in rows:
        found[key].append(Execution(status=status, duration_ms=duration, environment=environment))
    return found


def model_points(db: Session, project_id: int) -> List[Tuple[int, int]]:
    """(serial, wall) for the project's last MODEL_RUNS runs, every branch, with a duration and a result
    that ran. serial is the sum of the non-skipped results' durations."""
    recent = (
        select(Run.id, Run.duration_ms)
        .where(Run.project_id == project_id, Run.duration_ms > 0, Run.total > Run.skipped)
        .order_by(Run.started_at.desc(), Run.id.desc()).limit(MODEL_RUNS)
        .subquery()
    )
    serial = func.sum(case((RunResult.status != "skipped", RunResult.duration_ms), else_=0))
    rows = db.execute(
        select(recent.c.duration_ms, serial)
        .join(RunResult, RunResult.run_id == recent.c.id)
        .group_by(recent.c.id, recent.c.duration_ms)
    ).all()
    return [(int(s), int(wall)) for wall, s in rows if s and s > 0]


def estimate(db: Session, project_id: int, keys: Sequence[str], since: datetime,
             environment: Optional[str]) -> dict:
    keys = sorted({k.lower() for k in keys})
    found = executions(db, project_id, keys, since) if keys else {}  # in_list never gets an empty list
    model: Model = fit_model(model_points(db, project_id))
    return combine([durations_for(found.get(k, ()), environment) for k in keys], model)
