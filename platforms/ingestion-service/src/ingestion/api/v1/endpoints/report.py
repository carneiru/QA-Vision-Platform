"""POST /projects/{id}/analytics/report: every report section, scoped by the dashboard's filters."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.ingestion.analytics.report_period import PeriodError, check_period, choose_bucket
from src.ingestion.api.deps import READ_ROLES, ProjectAccess, get_db, require_project_role
from src.ingestion.api.v1.endpoints.analytics import _zone
from src.ingestion.schemas.report import ReportIn
from src.ingestion.service import report_service

router = APIRouter()  # mounted at /projects/{project_id}/analytics


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/report")
def report(
    body: ReportIn,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    zone = _zone(body.tz)
    now = _now()
    try:
        period = check_period(body.from_, body.to, zone, now)
    except PeriodError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    scope = report_service.Scope.from_request(access.project_id, body, period)
    try:
        report_service.limit_statement_time(db)
        return report_service.build_report(db, scope, body.sections, choose_bucket(body.bucket, period.days), now)
    except OperationalError as exc:
        if report_service.is_timeout(exc):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail={"code": "report_timeout", "message": report_service.REPORT_TIMEOUT_MESSAGE})
        raise
    finally:
        db.rollback()  # read-only: end the transaction (and its SET LOCAL) before the response is sent
