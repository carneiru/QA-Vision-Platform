import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError
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
    # Expiry must be checked BEFORE the invitation is claimed below: an expired invite
    # must never be marked accepted just because someone tried to use it.
    if _as_aware_utc(invitation.expires_at) <= datetime.now(timezone.utc):
        raise InvitationNotUsable("invitation expired")
    if get_organization(db, invitation.organization_id) is None:
        raise InvitationNotUsable("organization not found")

    organization_id = invitation.organization_id
    role = invitation.role

    # Single-use is enforced here, at the database, as a conditional UPDATE rather than
    # a read-then-write check: two concurrent accepts (different user_ids) racing past an
    # in-memory "accepted_at is None" check could otherwise both succeed, since
    # uq_org_member does not stop two different users from joining the same invite.
    # Only one request's UPDATE can match a still-unaccepted row.
    claimed = (
        db.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.token == token,
            OrganizationInvitation.accepted_at.is_(None),
        )
        .update({"accepted_at": datetime.now(timezone.utc)})
    )
    if not claimed:
        raise InvitationNotUsable("invitation not found or already accepted")

    # No _assert_can_grant_role call here on purpose: the grant policy was already
    # enforced once, against the INVITER's role, inside create_invitation above.
    # _create_member_row's own commit() is what persists the accepted_at claim above --
    # both land in one transaction, so a crash between "claimed" and "member created" is
    # no longer possible: either both happen or (via rollback below) neither does.
    try:
        member = _create_member_row(db, organization_id, user_id, role)
    except IntegrityError:
        # Same user double-clicking accept: two concurrent requests both pass
        # _create_member_row's existing-membership SELECT, and the second INSERT trips
        # uq_org_member. Convert to the same ValueError the duplicate-membership check
        # already raises, so the endpoint maps it to a clean 422 instead of a 500.
        db.rollback()
        raise ValueError("already a member")
    except ValueError:
        # Leaves the claim un-persisted too: nothing was committed, so the invitation
        # stays usable/pending for a later, valid accept.
        db.rollback()
        raise

    return member
