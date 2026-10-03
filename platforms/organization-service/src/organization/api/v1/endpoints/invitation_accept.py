from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.organization.api.deps import get_db, get_current_user_id
from src.organization.schemas.invitation import InvitationPreview
from src.organization.schemas.member import MemberOut
from src.organization.service import invitation_service
from src.organization.utils.auth_client import AuthServiceUnavailable

router = APIRouter()


@router.get("/{token}", response_model=InvitationPreview)
def preview_invitation(
    token: str,
    db: Session = Depends(get_db),
    _user_id: int = Depends(get_current_user_id),  # authenticated: only a signed-in invitee previews
):
    try:
        invitation, organization = invitation_service.preview_invitation(db, token)
    except invitation_service.InvitationNotUsable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return InvitationPreview(
        organization_id=organization.id,
        organization_name=organization.name,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
    )


@router.post("/{token}/accept", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def accept_invitation(
    token: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
        member = invitation_service.accept_invitation(db, token, user_id)
    except invitation_service.InvitationNotUsable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    except AuthServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return member
