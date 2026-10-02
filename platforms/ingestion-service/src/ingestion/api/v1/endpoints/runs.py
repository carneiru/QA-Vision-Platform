from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.ingestion.api.deps import (
    READ_ROLES, Caller, ProjectAccess, check_project_role, get_caller, get_db, require_project_role,
)
from src.ingestion.schemas.run import ChangedFileOut, ResultOut, RunDetail, RunOut
from src.ingestion.service import run_service

project_router = APIRouter()  # mounted at /projects/{project_id}/runs
router = APIRouter()          # mounted at /runs


@project_router.get("", response_model=list[RunOut])
def list_runs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    branch: Optional[str] = Query(None, max_length=255),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    return run_service.list_runs(db, access.project_id, limit, offset, branch)


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
    check_project_role(run.project_id, caller, READ_ROLES, "Run not found")
    results = run_service.list_results(db, run.id, status_filter)
    changes = run_service.list_changes(db, run.id)
    return RunDetail(
        **RunOut.model_validate(run).model_dump(),
        results=[ResultOut.model_validate(result) for result in results],
        changes=[ChangedFileOut.model_validate(f) for f in changes],
    )
