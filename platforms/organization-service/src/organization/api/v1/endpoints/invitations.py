from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.organization.api.deps import get_db, get_current_user_id, require_org_role
from src.organization.schemas.invitation import InvitationCreate, InvitationOut
from src.organization.service import invitation_service

router = APIRouter()


@router.post("", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
def create_invitation(
    org_id: int,
    payload: InvitationCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    granter_role: str = Depends(require_org_role("owner", "admin")),
):
    # get_current_user_id is also resolved inside require_org_role's dependency chain;
    # FastAPI caches dependency results per-request by callable identity, so the JWT is
    # only decoded once even though it's depended on here explicitly for invited_by_user_id.
    try:
        invitation = invitation_service.create_invitation(
            db, org_id, payload.email, payload.role, invited_by_user_id=user_id, granter_role=granter_role
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return invitation


@router.get("", response_model=list[InvitationOut])
def list_invitations(
    org_id: int,
    db: Session = Depends(get_db),
    _role: str = Depends(require_org_role("owner", "admin")),
):
    return invitation_service.list_invitations(db, org_id)


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    org_id: int,
    invitation_id: int,
    db: Session = Depends(get_db),
    _role: str = Depends(require_org_role("owner", "admin")),
):
    revoked = invitation_service.revoke_invitation(db, org_id, invitation_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
