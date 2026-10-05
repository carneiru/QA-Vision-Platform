from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.ingestion.api.deps import (
    READ_ROLES, Caller, ProjectAccess, check_project_role, get_caller, get_db, require_project_role,
)
from src.ingestion.api.v1.endpoints.analytics import NO_NUL
from src.ingestion.models.run import CI_PROVIDERS
from src.ingestion.schemas.run import ChangedFileOut, ComponentOut, ResultOut, RunDetail, RunOut
from src.ingestion.service import run_service

project_router = APIRouter()  # mounted at /projects/{project_id}/runs
router = APIRouter()          # mounted at /runs


@project_router.get("", response_model=list[RunOut])
def list_runs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    branch: Optional[str] = Query(None, max_length=255, pattern=NO_NUL),
    status_filter: Optional[Literal["failing", "passing"]] = Query(None, alias="status"),
    environment: Optional[str] = Query(None, max_length=100, pattern=NO_NUL),
    ci_provider: Optional[Literal[CI_PROVIDERS]] = Query(None),
    commit: Optional[str] = Query(None, pattern=r"^[0-9a-fA-F]{4,40}$"),
    pr: Optional[int] = Query(None, ge=1),
    author: Optional[str] = Query(None, max_length=255, pattern=NO_NUL),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    filters = run_service.RunFilters(
        branch=branch, status=status_filter, environment=environment, ci_provider=ci_provider,
        commit=commit, pr=pr, author=author, since=since, until=until,
    )
    return run_service.list_runs(db, access.project_id, limit, offset, filters)


@router.get("/{run_id}", response_model=RunDetail)
def get_run(
    run_id: int,
    status_filter: Optional[Literal["passed", "failed", "skipped", "errored"]] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_caller),
):
    run = run_service.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    # The project comes from the run row, never from the URL
    project_id = run.project_id
    # End the read-only transaction before the HTTP access check, so a slow
    # project-service never holds this connection out of the pool
    db.rollback()
    check_project_role(project_id, caller, READ_ROLES, "Run not found")
    results = run_service.list_results(db, run.id, status_filter)
    changes = run_service.list_changes(db, run.id)
    components = run_service.list_components(db, run.id)
    return RunDetail(
        **RunOut.model_validate(run).model_dump(),
        results=[ResultOut.model_validate(result) for result in results],
        changes=[ChangedFileOut.model_validate(f) for f in changes],
        components=[ComponentOut.model_validate(c) for c in components],
    )
