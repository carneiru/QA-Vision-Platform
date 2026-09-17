from datetime import datetime, timedelta, timezone
from src.organization.models.organization import Organization
from src.organization.models.invitation import OrganizationInvitation


def test_create_invitation(db):
    org = Organization(name="Acme", slug="acme", plan_tier="free")
    db.add(org)
    db.commit()
    db.refresh(org)

    invitation = OrganizationInvitation(
        organization_id=org.id,
        email="new@acme.test",
        role="member",
        invited_by_user_id=1,
        token="abc123",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    assert invitation.id is not None
    assert invitation.accepted_at is None
    assert invitation.email == "new@acme.test"
    assert invitation.role == "member"
