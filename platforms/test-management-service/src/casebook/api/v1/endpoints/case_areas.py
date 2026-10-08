"""GET /projects/{id}/case-areas: every active case, dictionary-encoded, for the report."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.casebook.api.deps import READ_ROLES, ProjectAccess, get_db, require_project_role
from src.casebook.service import case_area_service

router = APIRouter()  # mounted at /projects/{project_id}/case-areas


@router.get("")
def case_areas(db: Session = Depends(get_db), access: ProjectAccess = Depends(require_project_role(*READ_ROLES))):
    try:
        return case_area_service.case_areas(db, access.project_id, datetime.now(timezone.utc))
    except case_area_service.TooManyCases:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "too_many_cases",
            "message": f"This project has more cases than the report can join ({case_area_service.MAX_CASES:,})"})
