from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.organization.api.deps import get_db, get_current_user_id
from src.organization.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationOut
from src.organization.service import organization_service

router = APIRouter()


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
        org = organization_service.create_organization(
            db, name=payload.name, slug=payload.slug, plan_tier=payload.plan_tier, owner_user_id=user_id
        )
    except organization_service.OrganizationAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return org


@router.get("/{org_id}", response_model=OrganizationOut)
def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    org = organization_service.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.patch("/{org_id}", response_model=OrganizationOut)
def update_organization(
    org_id: int,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    org = organization_service.update_organization(db, org_id, **payload.model_dump(exclude_unset=True))
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    org_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    deleted = organization_service.soft_delete_organization(db, org_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
