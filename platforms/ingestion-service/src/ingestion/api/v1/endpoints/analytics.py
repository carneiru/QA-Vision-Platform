"""Read-only analytics over a project's runs, with the run endpoints' access rule."""
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from src.ingestion.analytics.flaky import rank_flaky
from src.ingestion.analytics.trends import daily, window_start
from src.ingestion.api.deps import READ_ROLES, ProjectAccess, get_db, require_project_role
from src.ingestion.schemas.analytics import FlakyOut, HistoryOut, StatsRowOut, TrendsOut
from src.ingestion.service import analytics_service

router = APIRouter()  # mounted at /projects/{project_id}/analytics


def _now() -> datetime:
    return datetime.now(timezone.utc)


# PostgreSQL cannot take NUL in a string parameter (SQLite, in the tests, would not notice)
NO_NUL = r"^[^\x00]*$"


@lru_cache(maxsize=1)
def _known_zones() -> frozenset:
    return frozenset(available_timezones())


def _zone(name: str) -> ZoneInfo:
    # Checked against the zone list rather than by trying ZoneInfo(name): a folder name such as
    # "America" raised PermissionError / IsADirectoryError (a 500), and a path is never a zone
    if name not in _known_zones():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown time zone: {name!r}")
    return ZoneInfo(name)


@router.get("/trends", response_model=TrendsOut)
def trends(
    days: int = Query(30, ge=1, le=365),
    tz: str = Query("UTC", min_length=1, max_length=64),
    branch: Optional[str] = Query(None, max_length=255, pattern=NO_NUL),
    environment: Optional[str] = Query(None, max_length=100, pattern=NO_NUL),
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
    search: Optional[str] = Query(None, max_length=200, pattern=NO_NUL),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    since = _now() - timedelta(days=days)
    return analytics_service.list_tests(db, access.project_id, since, sort=sort, search=search,
                                        limit=limit, offset=offset)


@router.get("/tests/{test_key}/history", response_model=HistoryOut)
def history(
    test_key: str = Path(..., pattern=r"^[0-9a-f]{64}$"),
    days: int = Query(30, ge=1, le=90),
    branch: Optional[str] = Query(None, max_length=255, pattern=NO_NUL),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    if not analytics_service.test_seen(db, access.project_id, test_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    since = _now() - timedelta(days=days)
    return analytics_service.test_history(db, access.project_id, test_key, since, branch, limit)


@router.get("/flaky", response_model=List[FlakyOut])
def flaky(
    # 30 at most: flaky detection sorts every execution in the window (measured in the README)
    window_days: int = Query(14, ge=1, le=30),
    min_runs: int = Query(5, ge=2, le=1000),
    min_flip_rate: float = Query(0.3, ge=0.0, le=1.0),
    branch: Optional[str] = Query(None, max_length=255, pattern=NO_NUL),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    since = _now() - timedelta(days=window_days)
    flips, mixed, latest = analytics_service.flaky_inputs(db, access.project_id, since, branch)
    return rank_flaky(flips, mixed, latest, min_runs=min_runs, min_flip_rate=min_flip_rate)
