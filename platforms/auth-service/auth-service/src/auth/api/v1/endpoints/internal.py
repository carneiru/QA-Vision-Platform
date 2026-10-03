"""Endpoints for other services, not for people.

Not routed by the gateway (its catch-all serves the SPA and /api/ answers the
JSON 404) and not in the public OpenAPI. Callers authenticate with HTTP Basic:
INTERNAL_API_USERNAME / INTERNAL_API_PASSWORD — the same pattern as
project-service's retention API. First consumer: organization-service's
member add, which previously needed a superuser's bearer token to ask
"does this user exist?"."""
import hmac
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.auth.config import settings
from src.auth.db.session import get_db
from src.auth.models.user import User

router = APIRouter()
_basic = HTTPBasic(auto_error=False)


class InternalUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool


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


@router.get("/users/{user_id}", response_model=InternalUser)
def get_user(user_id: int, _: None = Depends(require_internal_caller), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
