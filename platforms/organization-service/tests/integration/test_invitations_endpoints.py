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


def _make_org_named(client, owner_id: int, name: str, slug: str) -> int:
    """_make_org always creates "Acme"/"acme"; a second org needs distinct unique fields."""
    response = client.post(
        "/api/v1/organizations",
        json={"name": name, "slug": slug, "plan_tier": "free"},
        headers=_auth(owner_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_invitation(client, org_id: int, inviter_id: int, email: str = "new@example.com", role: str = "member"):
    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": email, "role": role},
        headers=_auth(inviter_id),
    )
    assert response.status_code == 201
    return response.json()


def _add_member(client, org_id: int, granter_id: int, user_id: int, role: str) -> None:
    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/{user_id}").mock(
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
        json={"email": "new@example.com", "role": "member"},
        headers=_auth(1),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "member"
    assert body["invited_by_user_id"] == 1
    assert "token" in body and len(body["token"]) > 20


def test_create_invitation_invalid_role_returns_422(client):
    org_id = _make_org(client, owner_id=1)

    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@example.com", "role": "sysadmin"},
        headers=_auth(1),
    )
    assert response.status_code == 422


@respx.mock
def test_admin_cannot_invite_as_owner(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=2, role="admin")

    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@example.com", "role": "owner"},
        headers=_auth(2),
    )
    assert response.status_code == 403


@respx.mock
def test_admin_can_invite_as_member(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=2, role="admin")

    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@example.com", "role": "member"},
        headers=_auth(2),
    )
    assert response.status_code == 201


@respx.mock
def test_plain_member_cannot_create_invitation(client):
    org_id = _make_org(client, owner_id=1)
    _add_member(client, org_id, granter_id=1, user_id=3, role="member")

    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@example.com", "role": "member"},
        headers=_auth(3),
    )
    assert response.status_code == 403


def test_owner_can_revoke_invitation(client):
    org_id = _make_org(client, owner_id=1)
    create_response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@example.com", "role": "member"},
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
        json={"email": "new@example.com", "role": "member"},
        headers=_auth(1),
    )
    token = create_response.json()["token"]

    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/5").mock(return_value=httpx.Response(200, json={"id": 5}))
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
        json={"email": "pending@example.com", "role": "member"},
        headers=_auth(1),
    )
    token = create_response.json()["token"]

    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/9").mock(return_value=httpx.Response(200, json={"id": 9}))
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
        json={"email": "new@example.com", "role": "owner"},
        headers=_auth(1),
    )
    assert create_response.status_code == 201
    token = create_response.json()["token"]

    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/6").mock(return_value=httpx.Response(200, json={"id": 6}))
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
        json={"email": "new@example.com", "role": "member"},
        headers=_auth(1),
    )
    token = create_response.json()["token"]

    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/7").mock(return_value=httpx.Response(200, json={"id": 7}))
    first = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(7))
    assert first.status_code == 201

    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/8").mock(return_value=httpx.Response(200, json={"id": 8}))
    second = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(8))
    assert second.status_code == 404


def test_accept_expired_invitation_returns_404(client, db):
    """Backdates expires_at directly via the db fixture -- there is no API to fast-forward
    time, so this is a deliberate, narrow exception to the real-HTTP-only test convention."""
    org_id = _make_org(client, owner_id=1)
    create_response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new@example.com", "role": "member"},
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
        json={"email": "new@example.com", "role": "member"},
        headers=_auth(1),
    )
    token = create_response.json()["token"]

    delete_response = client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(1))
    assert delete_response.status_code == 204

    response = client.post(f"/api/v1/invitations/{token}/accept", headers=_auth(9))
    assert response.status_code == 404


def test_create_invitation_rejects_malformed_email(client):
    """Pins EmailStr on the invited address. Without this, a revert to a plain `str` would
    break no test, and the address is the whole point of the row (a future notification
    service reads it)."""
    org_id = _make_org(client, owner_id=1)

    for bad_email in ["a@b", "   ", "not-an-email"]:
        response = client.post(
            f"/api/v1/organizations/{org_id}/invitations",
            json={"email": bad_email, "role": "member"},
            headers=_auth(1),
        )
        assert response.status_code == 422, f"expected 422 for {bad_email!r}"


def test_list_does_not_expose_tokens(client):
    """The raw token is returned ONLY by create. Exposing it to every admin via list would
    let an admin hand a pending owner-role invite to an account they control and mint an
    owner -- routing around the owner-only grant policy."""
    org_id = _make_org(client, owner_id=1)
    created = _create_invitation(client, org_id, inviter_id=1)
    assert "token" in created

    listed = client.get(f"/api/v1/organizations/{org_id}/invitations", headers=_auth(1))
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert "token" not in body[0]
    # the rest of the invitation is still visible, so the endpoint stays useful
    assert body[0]["email"] == "new@example.com"
    assert body[0]["id"] == created["id"]


@respx.mock
def test_plain_member_cannot_list_invitations(client):
    org_id = _make_org(client, owner_id=1)
    _create_invitation(client, org_id, inviter_id=1)
    _add_member(client, org_id, granter_id=1, user_id=3, role="member")

    response = client.get(f"/api/v1/organizations/{org_id}/invitations", headers=_auth(3))
    assert response.status_code == 403


def test_non_member_cannot_list_invitations(client):
    org_id = _make_org(client, owner_id=1)
    _create_invitation(client, org_id, inviter_id=1)

    response = client.get(f"/api/v1/organizations/{org_id}/invitations", headers=_auth(99))
    assert response.status_code == 404


def test_non_member_cannot_revoke_invitation(client):
    org_id = _make_org(client, owner_id=1)
    invitation = _create_invitation(client, org_id, inviter_id=1)

    response = client.delete(
        f"/api/v1/organizations/{org_id}/invitations/{invitation['id']}", headers=_auth(99)
    )
    assert response.status_code == 404


def test_invitation_routes_404_after_org_soft_deleted(client):
    org_id = _make_org(client, owner_id=1)
    invitation = _create_invitation(client, org_id, inviter_id=1)
    assert client.get(f"/api/v1/organizations/{org_id}/invitations", headers=_auth(1)).status_code == 200

    assert client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(1)).status_code == 204

    assert client.get(f"/api/v1/organizations/{org_id}/invitations", headers=_auth(1)).status_code == 404
    assert client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "other@example.com", "role": "member"},
        headers=_auth(1),
    ).status_code == 404
    assert client.delete(
        f"/api/v1/organizations/{org_id}/invitations/{invitation['id']}", headers=_auth(1)
    ).status_code == 404


def test_owner_cannot_revoke_another_orgs_invitation(client):
    org_a = _make_org(client, owner_id=1)
    invitation_a = _create_invitation(client, org_a, inviter_id=1)
    org_b = _make_org_named(client, owner_id=2, name="Beta", slug="beta")

    # user 2 owns org B and is not a member of org A at all
    response = client.delete(
        f"/api/v1/organizations/{org_b}/invitations/{invitation_a['id']}", headers=_auth(2)
    )
    assert response.status_code == 404

    # org A's invitation survives
    still_there = client.get(f"/api/v1/organizations/{org_a}/invitations", headers=_auth(1))
    assert [inv["id"] for inv in still_there.json()] == [invitation_a["id"]]


@respx.mock
def test_failed_accept_leaves_invitation_pending(client):
    """A failed accept must not burn the invite: the conditional-UPDATE claim and the member
    insert share one transaction, so a rollback un-claims the invitation too."""
    org_id = _make_org(client, owner_id=1)
    invitation = _create_invitation(client, org_id, inviter_id=1)
    _add_member(client, org_id, granter_id=1, user_id=4, role="member")

    # user 4 is already a member, so accepting fails
    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/4").mock(
        return_value=httpx.Response(200, json={"id": 4})
    )
    failed = client.post(f"/api/v1/invitations/{invitation['token']}/accept", headers=_auth(4))
    assert failed.status_code == 422

    # still pending, and still usable by someone else
    listed = client.get(f"/api/v1/organizations/{org_id}/invitations", headers=_auth(1))
    assert [inv["id"] for inv in listed.json()] == [invitation["id"]]

    respx.get(f"{settings.AUTH_SERVICE_URL}/internal/v1/users/5").mock(
        return_value=httpx.Response(200, json={"id": 5})
    )
    accepted = client.post(f"/api/v1/invitations/{invitation['token']}/accept", headers=_auth(5))
    assert accepted.status_code == 201
    assert accepted.json()["user_id"] == 5
