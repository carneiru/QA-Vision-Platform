from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.project.api.deps import EDIT_ROLES, READ_ROLES, ProjectAccess, get_db, require_project_role
from src.project.schemas.repository import RepositoryCreate, RepositoryOut
from src.project.service import repository_service

router = APIRouter()  # mounted at /projects/{project_id}/repositories


def _repository_or_404(db: Session, access: ProjectAccess, repo_id: int):
    repo = repository_service.get_repository(db, access.project, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repo


@router.get("", response_model=list[RepositoryOut])
def list_repositories(
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    return repository_service.list_repositories(db, access.project)


@router.post("", response_model=RepositoryOut, status_code=status.HTTP_201_CREATED)
def add_repository(
    payload: RepositoryCreate,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    try:
        return repository_service.add_repository(db, access.project, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except repository_service.DuplicateRepository as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/{repo_id}/verify", response_model=RepositoryOut)
def verify_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    return repository_service.reverify(db, _repository_or_404(db, access, repo_id))


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    repository_service.delete_repository(db, _repository_or_404(db, access, repo_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
