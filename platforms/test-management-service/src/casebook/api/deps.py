from typing import NamedTuple

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.casebook.db.session import get_db
from src.casebook.utils import project_client
from src.casebook.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

READ_ROLES = project_client.ROLES
EDIT_ROLES = ("owner", "admin", "member")


class Caller(NamedTuple):
    user_id: int
    token: str


class ProjectAccess(NamedTuple):
    project_id: int
    organization_id: int
    user_id: int
    role: str


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_caller(token: str = Depends(oauth2_scheme)) -> Caller:
    if token is None:
        raise _unauthorized()
    try:
        return Caller(user_id=int(decode_token(token)["sub"]), token=token)
    except (ValueError, KeyError, TypeError):
        raise _unauthorized()


def check_project_role(project_id: int, caller: Caller, roles: tuple, not_found_detail: str) -> ProjectAccess:
    try:
        info = project_client.get_project(project_id, caller.token)
    except project_client.ProjectNotFound:
        # never 403: a non-member must not learn that the project (or its data) exists
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    except project_client.InvalidCredentials:
        raise _unauthorized()
    except project_client.ProjectServiceUnavailable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Project service unavailable")
    if info.role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return ProjectAccess(
        project_id=project_id, organization_id=info.organization_id, user_id=caller.user_id, role=info.role
    )


def require_project_role(*roles: str):
    def dependency(project_id: int, caller: Caller = Depends(get_caller)) -> ProjectAccess:
        return check_project_role(project_id, caller, roles, "Project not found")

    return dependency


__all__ = [
    "get_db", "get_caller", "check_project_role", "require_project_role",
    "Caller", "ProjectAccess", "READ_ROLES", "EDIT_ROLES",
]
