# Organization Invitations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an organization owner/admin invite someone by email (who may not have a platform account yet) to join with a specific role, via a token-based invite link, without organization-service needing to know anything about auth-service's user table by email.

**Architecture:** Same layering as the rest of `organization-service` (model → schema → service → endpoint), same JWT bearer auth, same `require_org_role` dependency for role-gated routes. New `organization_invitations` table. The existing `member_service.add_member`'s owner-grants-owner/admin policy check is split into a reusable policy function and a reusable row-creation mechanism, so invitation creation and invitation acceptance each reuse the right half without duplicating or bypassing the security check.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, pytest, respx (existing stack — no new dependencies).

**Spec:** `docs/superpowers/specs/2026-09-17-organization-invitations-design.md`

## Global Constraints

- All ids are `Integer`, not UUID (established convention throughout this service).
- No email is ever sent by this service — API responses include the invite `token`, delivery is out of scope (spec's Constraints section).
- Accepting an invite requires ONLY a valid JWT and a valid token — no email-match verification against the invitee (spec's Constraints section: token possession is the security boundary).
- Do not modify anything under `platforms/auth-service/`.
- Every new/modified test must go through real HTTP requests via the `client` fixture (`TestClient`), not by calling service functions directly — this codebase's reviews have consistently required this. The one deliberate exception: backdating an invitation's `expires_at` directly via the `db` fixture in one test, because there is no API to fast-forward time (call this out explicitly where it happens).
- Run the FULL test suite (`pytest tests/ -v`, not a subset) before every commit in Task 2 and Task 3 — both touch/depend on the shared `member_service.py`.

---

### Task 1: `OrganizationInvitation` model + migration

**Files:**
- Create: `platforms/organization-service/src/organization/models/invitation.py`
- Modify: `platforms/organization-service/src/organization/models/__init__.py`
- Create: `platforms/organization-service/alembic/versions/003_add_organization_invitations.py`
- Create: `platforms/organization-service/tests/unit/test_invitation_model.py`
- Modify: `platforms/organization-service/tests/unit/test_migration.py`

**Interfaces:**
- Consumes: `src.organization.db.base.Base`
- Produces: `src.organization.models.invitation.OrganizationInvitation` (columns: `id`, `organization_id`, `email`, `role`, `invited_by_user_id`, `token`, `expires_at`, `created_at`, `accepted_at`)

- [ ] **Step 1: Write the failing model test**

```python
# tests/unit/test_invitation_model.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_invitation_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.organization.models.invitation'`

- [ ] **Step 3: Write `src/organization/models/invitation.py`**

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from src.organization.db.base import Base


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    invited_by_user_id = Column(Integer, nullable=False)
    token = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('owner','admin','member','viewer','billing_manager')", name="chk_invitation_role"
        ),
    )
```

- [ ] **Step 4: Register the model in `src/organization/models/__init__.py`**

Replace the file's full contents with:

```python
from src.organization.models.organization import Organization
from src.organization.models.member import OrganizationMember
from src.organization.models.invitation import OrganizationInvitation

__all__ = ["Organization", "OrganizationMember", "OrganizationInvitation"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_invitation_model.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Write the Alembic migration**

```python
# alembic/versions/003_add_organization_invitations.py
"""create organization_invitations

Revision ID: 003
Revises: 002
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "role IN ('owner','admin','member','viewer','billing_manager')", name="chk_invitation_role"
        ),
    )
    op.create_index("ix_organization_invitations_organization_id", "organization_invitations", ["organization_id"])
    op.create_index("ix_organization_invitations_token", "organization_invitations", ["token"], unique=True)


def downgrade() -> None:
    op.drop_table("organization_invitations")
```

- [ ] **Step 7: Add invitation coverage to `tests/unit/test_migration.py`**

Open `tests/unit/test_migration.py`. The existing `test_migration_creates_model_tables` and `test_migration_columns_match_models` are already generic over every table registered on `Base.metadata` — since Step 4 registered `OrganizationInvitation`, those two tests automatically cover the new table with no changes needed. Add one new test at the end of the file, mirroring the existing `test_migration_enforces_member_role_check`:

```python
def test_migration_enforces_invitation_role_check(migrated_engine):
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO organization_invitations"
                    " (organization_id, email, role, invited_by_user_id, token, expires_at)"
                    " VALUES (1, 'x@y.test', 'sysadmin', 1, 'tok', '2026-01-01T00:00:00+00:00')"
                )
            )
```

- [ ] **Step 8: Run test to verify it passes**

Run: `SECRET_KEY=test-secret pytest tests/ -v`
Expected: PASS (53 passed — the pre-existing 51 plus this task's 2 new tests: `test_create_invitation` and `test_migration_enforces_invitation_role_check`. `test_migration_columns_match_models` now also implicitly covers `organization_invitations`, with no changes needed to that test itself.)

- [ ] **Step 9: Commit**

```bash
git add platforms/organization-service/src/organization/models/invitation.py platforms/organization-service/src/organization/models/__init__.py platforms/organization-service/alembic/versions/003_add_organization_invitations.py platforms/organization-service/tests/unit/test_invitation_model.py platforms/organization-service/tests/unit/test_migration.py
git commit -m "feat(organization-service): add OrganizationInvitation model and migration"
```

---

### Task 2: Refactor `member_service` — split grant-policy from row-creation mechanism

**Why this task exists:** `add_member` currently has the owner-grants-owner/admin policy check inline, and `remove_member` has an equivalent inline check for removing a privileged member. Task 3's `accept_invitation` needs the row-creation mechanism WITHOUT re-running (or bypassing) a grant-policy check that already happened once, against the *inviter's* role, when the invitation was created. This task is a pure refactor: no behavior change for any existing caller, verified by the full existing suite staying green.

**Files:**
- Modify: `platforms/organization-service/src/organization/service/member_service.py` (full file)
- Create: `platforms/organization-service/tests/unit/test_member_service_internals.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `src.organization.service.member_service._assert_can_grant_role(granter_role: str, target_role: str) -> None` (raises `PermissionError` if `target_role` is `"owner"`/`"admin"` and `granter_role != "owner"`); `src.organization.service.member_service._create_member_row(db, org_id: int, user_id: int, role: str) -> OrganizationMember` (raises `ValueError` on invalid role / user not found / already a member — no grant-policy check). Both consumed by Task 3's `invitation_service.py`.
- `add_member`, `list_members`, `remove_member`'s public signatures are UNCHANGED — this task only changes what's inside them.

- [ ] **Step 1: Write the failing tests for the new internal functions**

```python
# tests/unit/test_member_service_internals.py
import pytest
from src.organization.models.organization import Organization
from src.organization.service.member_service import _assert_can_grant_role, _create_member_row


def test_assert_can_grant_role_allows_owner_granting_owner():
    _assert_can_grant_role("owner", "owner")  # does not raise


def test_assert_can_grant_role_allows_owner_granting_admin():
    _assert_can_grant_role("owner", "admin")  # does not raise


def test_assert_can_grant_role_allows_admin_granting_member():
    _assert_can_grant_role("admin", "member")  # does not raise


def test_assert_can_grant_role_blocks_admin_granting_owner():
    with pytest.raises(PermissionError):
        _assert_can_grant_role("admin", "owner")


def test_assert_can_grant_role_blocks_admin_granting_admin():
    with pytest.raises(PermissionError):
        _assert_can_grant_role("admin", "admin")


def test_create_member_row_rejects_invalid_role_before_any_network_call(db):
    """Invalid-role rejection must happen before the user_exists() HTTP call -- this test
    has no respx mock registered, so it also proves no HTTP call was attempted."""
    org = Organization(name="Acme", slug="acme", plan_tier="free")
    db.add(org)
    db.commit()
    db.refresh(org)

    with pytest.raises(ValueError, match="invalid role"):
        _create_member_row(db, org.id, user_id=1, role="sysadmin")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_member_service_internals.py -v`
Expected: FAIL with `ImportError: cannot import name '_assert_can_grant_role'`

- [ ] **Step 3: Rewrite `src/organization/service/member_service.py` in full**

```python
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


def _assert_can_grant_role(granter_role: str, target_role: str) -> None:
    """Only an owner may grant, or remove a member holding, an owner/admin-tier role.

    Shared by add_member (granting), remove_member (removing a privileged member is as much
    a takeover as granting the role), and invitation_service.create_invitation (checked once,
    against the inviter's role, at invite-creation time -- accept_invitation does not call
    this again, see _create_member_row below).
    """
    if target_role in ("owner", "admin") and granter_role != "owner":
        raise PermissionError(f"only an owner can grant or remove the '{target_role}' role")


def _create_member_row(db: Session, org_id: int, user_id: int, role: str) -> OrganizationMember:
    """The mechanism only -- no grant-policy check.

    add_member calls _assert_can_grant_role first, then this. invitation_service.accept_invitation
    calls this directly: the policy was already checked once, against the inviter's role, when the
    invitation was created -- re-checking it here against the ACCEPTER's role (who has none yet)
    would be wrong, not just redundant.
    """
    if role not in OrganizationMember.ROLES:
        raise ValueError(f"invalid role: {role}")
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


def add_member(db: Session, org_id: int, user_id: int, role: str, granter_role: str) -> OrganizationMember:
    _assert_can_grant_role(granter_role, role)
    return _create_member_row(db, org_id, user_id, role)


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

    _assert_can_grant_role(granter_role, member.role)

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
```

Note what changed vs. the current file: `add_member` no longer has its own inline `if role not in OrganizationMember.ROLES` check — `_create_member_row` already does that, so the duplicate was removed. `remove_member`'s inline privileged-member check is now a call to the same `_assert_can_grant_role` used by `add_member` (previously this was a second, separately-written copy of the same two-line check).

- [ ] **Step 4: Run the new tests, then the FULL suite**

Run: `pytest tests/unit/test_member_service_internals.py -v`
Expected: PASS (6 passed)

Run: `SECRET_KEY=test-secret pytest tests/ -v`
Expected: PASS (59 passed — the 53 from before this task, plus these 6 new ones) — this is a pure refactor, every pre-existing test must still pass unchanged. If anything that was passing before now fails, stop and fix before proceeding; do not adjust the pre-existing tests to match new behavior, since there should be no new behavior.

- [ ] **Step 5: Commit**

```bash
git add platforms/organization-service/src/organization/service/member_service.py platforms/organization-service/tests/unit/test_member_service_internals.py
git commit -m "refactor(organization-service): split member_service grant-policy from row-creation mechanism"
```

---

### Task 3: Invitation schemas, service, and endpoints

**Files:**
- Create: `platforms/organization-service/src/organization/schemas/invitation.py`
- Create: `platforms/organization-service/src/organization/service/invitation_service.py`
- Create: `platforms/organization-service/src/organization/api/v1/endpoints/invitations.py`
- Create: `platforms/organization-service/src/organization/api/v1/endpoints/invitation_accept.py`
- Modify: `platforms/organization-service/src/organization/api/v1/api.py`
- Create: `platforms/organization-service/tests/integration/test_invitations_endpoints.py`

**Interfaces:**
- Consumes: `require_org_role`, `get_current_user_id`, `get_db` (Task 1/existing); `_assert_can_grant_role`, `_create_member_row` (Task 2); `organization_service.get_organization` (existing); `OrganizationInvitation` (Task 1); `schemas.member.MemberOut` (existing, reused for the accept response)
- Produces: `invitation_service.create_invitation(db, org_id, email, role, invited_by_user_id, granter_role) -> OrganizationInvitation` (raises `ValueError` on invalid role, `PermissionError` if granter isn't owner and role is owner/admin); `invitation_service.list_invitations(db, org_id) -> list[OrganizationInvitation]` (pending only: not accepted, not expired); `invitation_service.revoke_invitation(db, org_id, invitation_id) -> bool`; `invitation_service.accept_invitation(db, token, user_id) -> OrganizationMember` (raises `invitation_service.InvitationNotUsable` if the token is missing/expired/already-accepted/organization-gone); routes under `/api/v1/organizations/{org_id}/invitations` (POST, GET, DELETE `/{id}`) and `/api/v1/invitations/{token}/accept` (POST)

- [ ] **Step 1: Write the failing endpoint tests**

```python
# tests/integration/test_invitations_endpoints.py
import jwt
import respx
import httpx
from datetime import datetime, timedelta, timezone
from src.organization.core.config import settings
from src.organization.models.invitation import OrganizationInvitation


def _token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _auth(user_id: int) -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _make_org(client, owner_id: int) -> int:
    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme", "slug": "acme", "plan_tier": "free"},
        headers=_auth(owner_id),
    )
    return response.json()["id"]


def _add_member(client, org_id: int, granter_id: int, user_id: int, role: str) -> None:
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/{user_id}").mock(
        return_value=httpx.Response(200, json={"id": user_id})
    )
    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": user_id, "role": role},
        headers=_auth(granter_id),
    )
    assert response.status_code == 201


def test_owner_can_create_invitation(client):
    org_id = _make_org(client, owner_id=1)

    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "member"},
        headers=_auth(1),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@acme.test"
    assert body["role"] == "member"
    assert body["invited_by_user_id"] == 1
    assert "token" in body and len(body["token"]) > 20


def test_create_invitation_invalid_role_returns_422(client):
    org_id = _make_org(client, owner_id=1)

    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "sysadmin"},
        headers=_auth(1),
    )
    assert response.status_code == 422


@respx.mock
def test_admin_cannot_invite_as_owner(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=2, role="admin")

    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "owner"},
        headers=_auth(2),
    )
    assert response.status_code == 403


@respx.mock
def test_admin_can_invite_as_member(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=2, role="admin")

    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "member"},
        headers=_auth(2),
    )
    assert response.status_code == 201


@respx.mock
def test_plain_member_cannot_create_invitation(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=3, role="member")

    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "member"},
        headers=_auth(3),
    )
    assert response.status_code == 403


def test_owner_can_revoke_invitation(client):
    org_id = _make_org(client, owner_id=1)
    create_response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "member"},
        headers=_auth(1),
    )
    invitation_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/organizations/{org_id}/invitations/{invitation_id}", headers=_auth(1))
    assert response.status_code == 204

    listed = client.get(f"/api/v1/organizations/{org_id}/invitations", headers=_auth(1))
    assert listed.json() == []


@respx.mock
def test_accept_invitation_creates_member_with_invited_role(client):
    org_id = _make_org(client, owner_id=1)
    create_response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "member"},
        headers=_auth(1),
    )
    token = create_response.json()["token"]

    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/5").mock(return_value=httpx.Response(200, json={"id": 5}))
    response = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(5))
    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == 5
    assert body["role"] == "member"
    assert body["organization_id"] == org_id


@respx.mock
def test_list_invitations_shows_only_pending(client):
    org_id = _make_org(client, owner_id=1)
    create_response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "pending@acme.test", "role": "member"},
        headers=_auth(1),
    )
    token = create_response.json()["token"]

    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/9").mock(return_value=httpx.Response(200, json={"id": 9}))
    accept_response = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(9))
    assert accept_response.status_code == 201

    listed = client.get(f"/api/v1/organizations/{org_id}/invitations", headers=_auth(1))
    assert listed.status_code == 200
    assert listed.json() == []


@respx.mock
def test_admin_invited_as_owner_by_real_owner_can_accept(client):
    """Proves the Task 2 policy/mechanism split: the ACCEPTER is not an owner, but the
    invite's role was already vetted against the INVITER's role at creation time."""
    org_id = _make_org(client, owner_id=1)
    create_response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "owner"},
        headers=_auth(1),
    )
    assert create_response.status_code == 201
    token = create_response.json()["token"]

    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/6").mock(return_value=httpx.Response(200, json={"id": 6}))
    response = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(6))
    assert response.status_code == 201
    assert response.json()["role"] == "owner"


def test_accept_nonexistent_token_returns_404(client):
    response = client.post("/api/v1/invitations/not-a-real-token/accept", headers=_auth(9))
    assert response.status_code == 404


@respx.mock
def test_accept_already_accepted_invitation_returns_404(client):
    org_id = _make_org(client, owner_id=1)
    create_response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "member"},
        headers=_auth(1),
    )
    token = create_response.json()["token"]

    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/7").mock(return_value=httpx.Response(200, json={"id": 7}))
    first = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(7))
    assert first.status_code == 201

    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/8").mock(return_value=httpx.Response(200, json={"id": 8}))
    second = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(8))
    assert second.status_code == 404


def test_accept_expired_invitation_returns_404(client, db):
    """Backdates expires_at directly via the db fixture -- there is no API to fast-forward
    time, so this is a deliberate, narrow exception to the real-HTTP-only test convention."""
    org_id = _make_org(client, owner_id=1)
    create_response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "member"},
        headers=_auth(1),
    )
    invitation_id = create_response.json()["id"]

    invitation = db.query(OrganizationInvitation).filter(OrganizationInvitation.id == invitation_id).first()
    invitation.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()

    token = create_response.json()["token"]
    response = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(9))
    assert response.status_code == 404


def test_accept_into_soft_deleted_org_returns_404(client):
    org_id = _make_org(client, owner_id=1)
    create_response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@acme.test", "role": "member"},
        headers=_auth(1),
    )
    token = create_response.json()["token"]

    delete_response = client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(1))
    assert delete_response.status_code == 204

    response = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(9))
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SECRET_KEY=test-secret pytest tests/integration/test_invitations_endpoints.py -v`
Expected: FAIL with 404s (no `/invitations` routes registered yet) or collection errors (schemas/service modules don't exist yet)

- [ ] **Step 3: Write `src/organization/schemas/invitation.py`**

```python
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field
from src.organization.models.member import OrganizationMember

Role = Literal[OrganizationMember.ROLES]  # type: ignore[valid-type]


class InvitationCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    role: Role = "member"


class InvitationOut(BaseModel):
    id: int
    organization_id: int
    email: str
    role: str
    invited_by_user_id: int
    token: str
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Write `src/organization/service/invitation_service.py`**

```python
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
```

- [ ] **Step 5: Write `src/organization/api/v1/endpoints/invitations.py`**

```python
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
```

- [ ] **Step 6: Write `src/organization/api/v1/endpoints/invitation_accept.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.organization.api.deps import get_db, get_current_user_id
from src.organization.schemas.member import MemberOut
from src.organization.service import invitation_service
from src.organization.utils.auth_client import AuthServiceUnavailable

router = APIRouter()


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
```

- [ ] **Step 7: Wire both routers in `src/organization/api/v1/api.py`**

```python
from fastapi import APIRouter
from src.organization.api.v1.endpoints import organizations, members, invitations, invitation_accept

api_router = APIRouter()
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(members.router, prefix="/organizations/{org_id}/members", tags=["members"])
api_router.include_router(invitations.router, prefix="/organizations/{org_id}/invitations", tags=["invitations"])
api_router.include_router(invitation_accept.router, prefix="/invitations", tags=["invitations"])

__all__ = ["api_router"]
```

- [ ] **Step 8: Run test to verify it passes**

Run: `SECRET_KEY=test-secret pytest tests/integration/test_invitations_endpoints.py -v`
Expected: PASS (13 passed)

Then run the FULL suite (this task's endpoints sit behind `require_org_role` and reuse `member_service` internals from Task 2 — confirm nothing else regressed):

Run: `SECRET_KEY=test-secret pytest tests/ -v`
Expected: PASS (72 passed — 59 from before this task, plus these 13 new ones)

- [ ] **Step 9: Commit**

```bash
git add platforms/organization-service/src/organization/schemas/invitation.py platforms/organization-service/src/organization/service/invitation_service.py platforms/organization-service/src/organization/api/v1/endpoints/invitations.py platforms/organization-service/src/organization/api/v1/endpoints/invitation_accept.py platforms/organization-service/src/organization/api/v1/api.py platforms/organization-service/tests/integration/test_invitations_endpoints.py
git commit -m "feat(organization-service): add invitation create/list/revoke/accept endpoints"
```

---

### Task 4: Full suite pass, README update

**Files:**
- Modify: `platforms/organization-service/README.md`

**Interfaces:**
- Consumes: nothing new — this task only verifies and documents Tasks 1-3

- [ ] **Step 1: Run the entire test suite**

Run: `cd platforms/organization-service && SECRET_KEY=test-secret pytest -v`
Expected: PASS, all tests from Tasks 1-3 green, zero failures/errors (72 passed)

- [ ] **Step 2: Update `README.md`**

Replace the file's full contents with:

```markdown
# Organization Service

Manages organizations (tenants) and their memberships for QA Vision Platform.

## Responsibilities

- Organization CRUD (`/api/v1/organizations`)
- Membership management (`/api/v1/organizations/{org_id}/members`) with roles:
  `owner`, `admin`, `member`, `viewer`, `billing_manager`. Only an owner may grant or
  remove a member with the `owner`/`admin` role.
- Email-based invitations (`/api/v1/organizations/{org_id}/invitations` to create/list/revoke,
  `/api/v1/invitations/{token}/accept` to accept). This service does not send email -- the
  create response includes the invite `token`; delivering it is a separate concern (a
  frontend or notification-service's job). Whoever holds a valid, unexpired, unused invite
  token and is logged in may accept it; there is no email-match check against the invitee.
- Validates member `user_id`s against auth-service over HTTP before adding them

Known limitation: the `user_id` existence check assumes auth-service returns `404` for an
unknown user id, which it does not yet do cleanly — resolving it requires a change in
auth-service and is tracked as a follow-up.

## Auth model

This service does not issue tokens. It trusts JWTs signed by auth-service
(shared `SECRET_KEY`/`HS256`) and reads the user id from the `sub` claim.

## Out of scope (see docs/superpowers/specs/2026-09-16-organization-service-core-design.md)

- `organization_settings` (SSO/MFA/session config per org)

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env  # set SECRET_KEY to match auth-service's
alembic upgrade head
uvicorn src.organization.api.main:app --reload
```

## Testing

```bash
SECRET_KEY=test-secret pytest -v
```
```

- [ ] **Step 3: Commit**

```bash
git add platforms/organization-service/README.md
git commit -m "docs(organization-service): document invitations in README"
```
