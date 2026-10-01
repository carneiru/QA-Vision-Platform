"""Read-only analytics over a project's runs, with the run endpoints' access rule."""
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.ingestion.analytics.trends import daily, window_start
from src.ingestion.api.deps import READ_ROLES, ProjectAccess, get_db, require_project_role
from src.ingestion.schemas.analytics import StatsRowOut, TrendsOut
from src.ingestion.service import analytics_service

router = APIRouter()  # mounted at /projects/{project_id}/analytics


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        # ValueError: not a valid zone key at all (e.g. a path); never read as a file
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown time zone: {name!r}")


@router.get("/trends", response_model=TrendsOut)
def trends(
    days: int = Query(30, ge=1, le=365),
    tz: str = Query("UTC", min_length=1, max_length=64),
    branch: Optional[str] = Query(None, max_length=255),
    environment: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    zone = _zone(tz)
    now = _now()
    rows = analytics_service.trend_rows(db, access.project_id, window_start(now, days, zone), branch, environment)
    return {"tz": tz, "days": daily(rows, now, days, zone)}


@router.get("/tests", response_model=List[StatsRowOut])
def tests(
    days: int = Query(30, ge=1, le=90),
    sort: Literal["failures", "duration", "name"] = Query("failures"),
    search: Optional[str] = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    since = _now() - timedelta(days=days)
    return analytics_service.list_tests(db, access.project_id, since, sort=sort, search=search,
                                        limit=limit, offset=offset)
