"""Endpoints for other services, not for people.

Not routed by the gateway (its catch-all answers 404) and not in the public OpenAPI. Callers
authenticate with HTTP Basic: INTERNAL_API_USERNAME / INTERNAL_API_PASSWORD.
"""
import hmac
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.project.core.config import settings
from src.project.db.session import get_db
from src.project.models.project import Project
from src.project.schemas.settings import settings_view

router = APIRouter()
_basic = HTTPBasic(auto_error=False)


class ProjectRetention(BaseModel):
    project_id: int
    result_retention_days: int
    deleted: bool
    # When it was deleted: the retention job waits a grace period before emptying it
    deleted_at: Optional[datetime] = None


class RetentionList(BaseModel):
    projects: list[ProjectRetention]


def _same(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def require_internal_caller(credentials: Optional[HTTPBasicCredentials] = Depends(_basic)) -> None:
    if not settings.INTERNAL_API_PASSWORD:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal API is not configured")
    # Both parts are always compared, so the timing does not tell which one was wrong
    user_ok = credentials is not None and _same(credentials.username, settings.INTERNAL_API_USERNAME)
    password_ok = credentials is not None and _same(credentials.password, settings.INTERNAL_API_PASSWORD)
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.get("/projects/retention", response_model=RetentionList)
def list_retention(_: None = Depends(require_internal_caller), db: Session = Depends(get_db)):
    """Every project, deleted ones included, with its effective retention period."""
    projects = db.query(Project).order_by(Project.id).all()
    return RetentionList(projects=[
        ProjectRetention(
            project_id=project.id,
            result_retention_days=settings_view(project.settings).result_retention_days,
            deleted=project.deleted_at is not None,
            deleted_at=project.deleted_at,
        )
        for project in projects
    ])
