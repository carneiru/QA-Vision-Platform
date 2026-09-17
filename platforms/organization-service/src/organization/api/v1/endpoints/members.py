from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.organization.api.deps import get_db, get_current_user_id, require_org_role
from src.organization.schemas.member import MemberCreate, MemberOut
from src.organization.service import member_service
from src.organization.utils.auth_client import AuthServiceUnavailable

router = APIRouter()


@router.post("", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    org_id: int,
    payload: MemberCreate,
    db: Session = Depends(get_db),
    granter_role: str = Depends(require_org_role("owner", "admin")),
):
    try:
        member = member_service.add_member(db, org_id, payload.user_id, payload.role, granter_role)
    except AuthServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return member


@router.get("", response_model=list[MemberOut])
def list_members(
    org_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    role = member_service.get_role(db, org_id, user_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a member of this organization")
    return member_service.list_members(db, org_id)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    org_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    _role: str = Depends(require_org_role("owner", "admin")),
):
    removed = member_service.remove_member(db, org_id, member_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
