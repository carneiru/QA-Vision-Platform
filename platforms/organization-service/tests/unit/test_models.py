from src.organization.models.organization import Organization
from src.organization.models.member import OrganizationMember


def test_create_organization_and_member(db):
    org = Organization(name="Acme", slug="acme", plan_tier="free")
    db.add(org)
    db.commit()
    db.refresh(org)

    member = OrganizationMember(organization_id=org.id, user_id=7, role="owner", status="active")
    db.add(member)
    db.commit()
    db.refresh(member)

    assert org.id is not None
    assert org.deleted_at is None
    assert member.organization_id == org.id
    assert member.user_id == 7
    assert member.role == "owner"
