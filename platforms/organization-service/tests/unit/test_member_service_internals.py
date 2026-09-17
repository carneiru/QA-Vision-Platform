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
