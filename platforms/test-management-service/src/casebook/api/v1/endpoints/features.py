"""GET /projects/{id}/features and /features/detail: cases grouped by .feature file, and a file's raw text."""
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.casebook.api.deps import READ_ROLES, ProjectAccess, get_db, require_project_role
from src.casebook.api.v1.endpoints.cases import NO_NUL
from src.casebook.schemas.case import Priority, Status
from src.casebook.schemas.feature import FeatureDetail, FeatureList
from src.casebook.service import feature_service

router = APIRouter()  # mounted at /projects/{project_id}/features


@router.get("", response_model=FeatureList)
def list_features(
    search: Optional[str] = Query(None, max_length=200, pattern=NO_NUL),
    search_in: Literal["feature", "scenario", "both"] = Query("both"),
    label: List[str] = Query([], max_length=20),
    status_filter: Optional[Status] = Query(None, alias="status"),
    priority: Optional[Priority] = Query(None),
    folder: Optional[str] = Query(None, max_length=500, pattern=NO_NUL),
    linked: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    return feature_service.list_features(
        db, access.project_id, search=search, search_in=search_in, labels=label, status=status_filter,
        priority=priority, include_archived=False, folder=folder, linked=linked, limit=limit, offset=offset)


@router.get("/detail", response_model=FeatureDetail)
def feature_detail(
    path: str = Query(..., min_length=1, max_length=500, pattern=NO_NUL),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    detail = feature_service.feature_detail(db, access.project_id, path)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")
    return detail
