import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from src.organization.models.invitation import OrganizationInvitation
from src.organization.models.member import OrganizationMember
from src.organization.service.member_service import _assert_can_grant_role, _create_member_row
from src.organization.service.organization_service import get_organization

INVITATION_EXPIRY = timedelta(days=7)


class InvitationNotUsable(Exception):
    """Raised when a token doesn't resolve to a usable (found, unexpired, unaccepted,
    organization-still-exists) invitation. The endpoint maps every case to 404 without
    distinguishing which -- see the design spec's Error Handling section."""


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes for DateTime(timezone=True) columns even though
    Postgres would return timezone-aware ones. Normalize before comparing against
    datetime.now(timezone.utc), or the comparison raises TypeError on SQLite."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def create_invitation(
    db: Session, org_id: int, email: str, role: str, invited_by_user_id: int, granter_role: str
) -> OrganizationInvitation:
    if role not in OrganizationMember.ROLES:
        raise ValueError(f"invalid role: {role}")
    _assert_can_grant_role(granter_role, role)

    invitation = OrganizationInvitation(
        organization_id=org_id,
        email=email,
        role=role,
        invited_by_user_id=invited_by_user_id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc) + INVITATION_EXPIRY,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


def list_invitations(db: Session, org_id: int) -> list[OrganizationInvitation]:
    now = datetime.now(timezone.utc)
    return (
        db.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.organization_id == org_id,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.expires_at > now,
        )
        .all()
    )


def revoke_invitation(db: Session, org_id: int, invitation_id: int) -> bool:
    invitation = (
        db.query(OrganizationInvitation)
        .filter(OrganizationInvitation.id == invitation_id, OrganizationInvitation.organization_id == org_id)
        .first()
    )
    if invitation is None:
        return False
    db.delete(invitation)
    db.commit()
    return True


def accept_invitation(db: Session, token: str, user_id: int) -> OrganizationMember:
    invitation = db.query(OrganizationInvitation).filter(OrganizationInvitation.token == token).first()
    if invitation is None:
        raise InvitationNotUsable("invitation not found")
    if invitation.accepted_at is not None:
        raise InvitationNotUsable("invitation already accepted")
    if _as_aware_utc(invitation.expires_at) <= datetime.now(timezone.utc):
        raise InvitationNotUsable("invitation expired")
    if get_organization(db, invitation.organization_id) is None:
        raise InvitationNotUsable("organization not found")

    # No _assert_can_grant_role call here on purpose: the grant policy was already
    # enforced once, against the INVITER's role, inside create_invitation above.
    member = _create_member_row(db, invitation.organization_id, user_id, invitation.role)

    invitation.accepted_at = datetime.now(timezone.utc)
    db.commit()
    return member
