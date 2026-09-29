from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.ingestion.api.deps import EDIT_ROLES, READ_ROLES, ProjectAccess, get_db, require_project_role
from src.ingestion.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from src.ingestion.service import api_key_service

router = APIRouter()  # mounted at /projects/{project_id}/api-keys


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    row, key = api_key_service.create_key(db, access, payload.name)
    return ApiKeyCreated(id=row.id, name=row.name, key_prefix=row.key_prefix, key=key, created_at=row.created_at)


@router.get("", response_model=list[ApiKeyOut])
def list_api_keys(
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    return api_key_service.list_keys(db, access.project_id)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    if not api_key_service.revoke_key(db, access.project_id, key_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
