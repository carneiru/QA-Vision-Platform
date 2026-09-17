from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.organization.models.organization import Organization
from src.organization.models.member import OrganizationMember


def create_organization(db: Session, name: str, slug: str, plan_tier: str, owner_user_id: int) -> Organization:
    org = Organization(name=name, slug=slug, plan_tier=plan_tier)
    db.add(org)
    db.flush()  # assign org.id without committing yet

    owner = OrganizationMember(
        organization_id=org.id,
        user_id=owner_user_id,
        role="owner",
        status="active",
    )
    db.add(owner)
    db.commit()
    db.refresh(org)
    return org


def get_organization(db: Session, org_id: int) -> Optional[Organization]:
    return (
        db.query(Organization)
        .filter(Organization.id == org_id, Organization.deleted_at.is_(None))
        .first()
    )


def update_organization(db: Session, org_id: int, **fields) -> Optional[Organization]:
    org = get_organization(db, org_id)
    if org is None:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(org, key, value)
    db.commit()
    db.refresh(org)
    return org


def soft_delete_organization(db: Session, org_id: int) -> bool:
    org = get_organization(db, org_id)
    if org is None:
        return False
    org.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return True
