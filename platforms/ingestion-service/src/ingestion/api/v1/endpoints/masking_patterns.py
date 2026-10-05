from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.ingestion.api.deps import EDIT_ROLES, READ_ROLES, ProjectAccess, get_db, require_project_role
from src.ingestion.schemas.masking_pattern import (
    MaskingPatternCreate, MaskingPatternOut, MaskingPreviewIn, MaskingPreviewOut,
)
from src.ingestion.service import ingest_service, masking_pattern_service
from src.ingestion.utils.redaction import marker

router = APIRouter()  # mounted at /projects/{project_id}/masking-patterns


@router.get("", response_model=list[MaskingPatternOut])
def list_masking_patterns(
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    return masking_pattern_service.list_patterns(db, access.project_id)


@router.post("", response_model=MaskingPatternOut, status_code=status.HTTP_201_CREATED)
def add_masking_pattern(
    payload: MaskingPatternCreate,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    try:
        return masking_pattern_service.add_pattern(db, access.project_id, payload.name, payload.pattern, access.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except masking_pattern_service.DuplicatePattern as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/preview", response_model=MaskingPreviewOut)
def preview_masking_pattern(
    payload: MaskingPreviewIn,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    """The sample as it would be stored with this pattern added (built-in masking and the
    project's other patterns included), and how many times this pattern matched. Nothing is saved."""
    try:
        pattern = masking_pattern_service.validate(payload.name, payload.pattern)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    others = tuple(p for p in masking_pattern_service.compiled_for(db, access.project_id) if p.name != pattern.name)
    masked, _ = ingest_service.mask(payload.sample, others + (pattern,))
    return MaskingPreviewOut(masked=masked, matches=masked.count(marker(pattern.name)))


@router.delete("/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_masking_pattern(
    pattern_id: int,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    if not masking_pattern_service.delete_pattern(db, access.project_id, pattern_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Masking pattern not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
