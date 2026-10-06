"""Read-only analytics over a project's runs, with the run endpoints' access rule."""
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from src.ingestion.analytics import rollup
from src.ingestion.analytics.flaky import rank_flaky
from src.ingestion.analytics.trends import bucketed, daily, window_start
from src.ingestion.api.deps import EDIT_ROLES, READ_ROLES, ProjectAccess, get_db, require_project_role
from src.ingestion.schemas.analytics import (
    BranchStatsOut, FlakyOut, HistoryOut, MuteIn, StatsRowOut, TrendsOut,
)
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
    bucket: Literal["day", "week", "month"] = Query("day"),
    branch: Optional[str] = Query(None, max_length=255, pattern=NO_NUL),
    environment: Optional[str] = Query(None, max_length=100, pattern=NO_NUL),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    zone = _zone(tz)
    now = _now()
    rows = analytics_service.trend_rows(db, access.project_id, window_start(now, days, zone), branch, environment)
    return {"tz": tz, "bucket": bucket, "days": bucketed(rows, now, days, zone, bucket)}


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


@router.get("/branches", response_model=List[BranchStatsOut])
def branches(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    since = _now() - timedelta(days=days)
    return analytics_service.branch_stats(db, access.project_id, since, limit)


@router.get("/flaky", response_model=List[FlakyOut])
def flaky(
    # 90 now that windows recombine from the daily rollups; the live fallback
    # (a project the rollup job has not visited yet) still scans executions
    window_days: int = Query(14, ge=1, le=90),
    min_runs: int = Query(5, ge=2, le=1000),
    min_flip_rate: float = Query(0.3, ge=0.0, le=1.0),
    branch: Optional[str] = Query(None, max_length=255, pattern=NO_NUL),
    include_muted: bool = Query(False),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    since = _now() - timedelta(days=window_days)
    if rollup.has_rollups(db, access.project_id):
        flips, mixed, latest = rollup.rollup_inputs(db, access.project_id, since.date(), branch)
    else:
        flips, mixed, latest = analytics_service.flaky_inputs(db, access.project_id, since, branch)
    items = rank_flaky(flips, mixed, latest, min_runs=min_runs, min_flip_rate=min_flip_rate)
    muted = analytics_service.muted_keys(db, access.project_id)
    if include_muted:
        for item in items:
            item["muted"] = item["test_key"] in muted
        return items
    return [item for item in items if item["test_key"] not in muted]


@router.put("/flaky/mute", status_code=status.HTTP_204_NO_CONTENT)
def mute_flaky(
    payload: MuteIn,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    analytics_service.mute_test(db, access.project_id, payload.test_key, access.user_id)


@router.delete("/flaky/mute/{test_key}", status_code=status.HTTP_204_NO_CONTENT)
def unmute_flaky(
    test_key: str = Path(max_length=500, pattern=NO_NUL),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    if not analytics_service.unmute_test(db, access.project_id, test_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test is not muted")


@router.get("/latest-keys")
def latest_keys(
    status: Literal["passed", "failed", "skipped", "any"] = Query(...),
    branch: Optional[str] = Query(None, max_length=255, pattern=NO_NUL),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    """Keys of the tests whose latest result has `status`; the dashboard passes them to test-management."""
    return {"keys": analytics_service.latest_keys(db, access.project_id, status, branch)}
