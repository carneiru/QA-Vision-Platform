from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.project.api.deps import (
    EDIT_ROLES, MANAGE_ROLES, READ_ROLES, OrgAccess, ProjectAccess, get_db, require_org_role, require_project_role,
)
from src.project.models.project import Project
from src.project.schemas.project import LegalHoldIn, LegalHoldOut, ProjectCreate, ProjectOut, ProjectUpdate
from src.project.schemas.settings import settings_view
from src.project.service import project_service

org_router = APIRouter()   # mounted at /organizations/{org_id}/projects
router = APIRouter()       # mounted at /projects


def _out(project: Project, role: str) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        settings=settings_view(project.settings),
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        my_role=role,
        legal_hold=(
            LegalHoldOut(since=project.legal_hold_at, by=project.legal_hold_by, reason=project.legal_hold_reason)
            if project.legal_hold_at is not None else None
        ),
    )


@org_router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    access: OrgAccess = Depends(require_org_role(*MANAGE_ROLES)),
):
    try:
        project = project_service.create_project(db, access.org_id, access.user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except project_service.DuplicateProject as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _out(project, access.role)


@org_router.get("", response_model=list[ProjectOut])
def list_projects(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    access: OrgAccess = Depends(require_org_role(*READ_ROLES)),
):
    projects = project_service.list_projects(db, access.org_id, limit, offset)
    return [_out(project, access.role) for project in projects]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(access: ProjectAccess = Depends(require_project_role(*READ_ROLES))):
    return _out(access.project, access.role)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*MANAGE_ROLES)),
):
    try:
        project = project_service.update_project(db, access.project, payload)
    except project_service.DuplicateProject as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _out(project, access.role)


@router.patch("/{project_id}/settings", response_model=ProjectOut)
def update_settings(
    patch: dict = Body(...),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    try:
        project = project_service.update_settings(db, access.project, patch)
    except ValidationError as exc:
        db.rollback()
        detail = [{"loc": list(error["loc"]), "msg": error["msg"]} for error in exc.errors()]
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _out(project, access.role)


@router.put("/{project_id}/legal-hold", response_model=ProjectOut)
def place_legal_hold(
    payload: LegalHoldIn,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*MANAGE_ROLES)),
):
    """Retention deletes nothing of a held project until the hold is released."""
    project = project_service.place_legal_hold(db, access.project, access.user_id, payload.reason)
    return _out(project, access.role)


@router.delete("/{project_id}/legal-hold", response_model=ProjectOut)
def release_legal_hold(
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*MANAGE_ROLES)),
):
    return _out(project_service.release_legal_hold(db, access.project), access.role)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*MANAGE_ROLES)),
):
    project_service.soft_delete(db, access.project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
