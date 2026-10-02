from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.organization.models.organization import Organization
from src.organization.models.member import OrganizationMember


class OrganizationAlreadyExists(Exception):
    """Raised when an organization's name or slug collides with an existing one."""


def create_organization(db: Session, name: str, slug: str, plan_tier: str, owner_user_id: int) -> Organization:
    org = Organization(name=name, slug=slug, plan_tier=plan_tier)
    db.add(org)
    try:
        db.flush()  # assign org.id without committing yet

        owner = OrganizationMember(
            organization_id=org.id,
            user_id=owner_user_id,
            role="owner",
            status="active",
        )
        db.add(owner)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise OrganizationAlreadyExists(f"Organization with name={name!r} or slug={slug!r} already exists")
    db.refresh(org)
    return org


def get_organization(db: Session, org_id: int) -> Optional[Organization]:
    return (
        db.query(Organization)
        .filter(Organization.id == org_id, Organization.deleted_at.is_(None))
        .first()
    )


def list_organizations_for_user(db: Session, user_id: int) -> list[tuple[Organization, str]]:
    """Organizations where the user is an active member, with their role, by name."""
    return (
        db.query(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
            Organization.deleted_at.is_(None),
        )
        .order_by(Organization.name.asc())
        .all()
    )


def update_organization(db: Session, org_id: int, **fields) -> Optional[Organization]:
    org = get_organization(db, org_id)
    if org is None:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(org, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise OrganizationAlreadyExists("Organization with that name or slug already exists")
    db.refresh(org)
    return org


def soft_delete_organization(db: Session, org_id: int) -> bool:
    org = get_organization(db, org_id)
    if org is None:
        return False
    org.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return True
