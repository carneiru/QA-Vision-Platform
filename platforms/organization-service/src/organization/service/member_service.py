from typing import Optional
from sqlalchemy.orm import Session
from src.organization.models.member import OrganizationMember
from src.organization.utils.auth_client import user_exists


def get_role(db: Session, org_id: int, user_id: int) -> Optional[str]:
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
        .first()
    )
    return member.role if member else None


def add_member(db: Session, org_id: int, user_id: int, role: str, granter_role: str) -> OrganizationMember:
    if role not in OrganizationMember.ROLES:
        raise ValueError(f"invalid role: {role}")
    if role in ("owner", "admin") and granter_role != "owner":
        raise PermissionError(f"only an owner can grant the '{role}' role")
    if not user_exists(user_id):
        raise ValueError("user not found")

    existing = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user_id)
        .first()
    )
    if existing:
        raise ValueError("already a member")

    member = OrganizationMember(organization_id=org_id, user_id=user_id, role=role, status="active")
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def list_members(db: Session, org_id: int) -> list[OrganizationMember]:
    return (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == org_id, OrganizationMember.status == "active")
        .all()
    )


def remove_member(db: Session, org_id: int, member_id: int, granter_role: str) -> bool:
    member = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.id == member_id, OrganizationMember.organization_id == org_id)
        .first()
    )
    if member is None:
        return False

    # removing a privileged member is as much a takeover as granting the role, so it needs the same guard
    if member.role in ("owner", "admin") and granter_role != "owner":
        raise PermissionError(f"only an owner can remove a member with the '{member.role}' role")

    if member.role == "owner":
        owner_count = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.role == "owner",
                OrganizationMember.status == "active",
            )
            .count()
        )
        if owner_count <= 1:
            raise ValueError("cannot remove the last owner")

    db.delete(member)
    db.commit()
    return True
