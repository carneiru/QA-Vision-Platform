"""Password reset (forgot -> emailed single-use link -> new password) and password
change for a signed-in user. Both end every other session: whoever had the old
password must not keep a refresh token that outlives it."""
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

from src.auth.models.password_reset import PasswordReset
from src.auth.models.user import User

FORGOT = "/api/v1/auth/forgot-password"
RESET = "/api/v1/auth/reset-password"
CHANGE = "/api/v1/auth/change-password"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh-token"
OLD = "securepassword123"
NEW = "brand-new-password-456"


def _token_from_log(caplog) -> str:
    match = re.search(r"/reset-password\?token=([A-Za-z0-9_\-]+)", caplog.text)
    assert match, f"no reset link was logged: {caplog.text!r}"
    return match.group(1)


def _login(client, email, password):
    return client.post(LOGIN, json={"email": email, "password": password})


def test_unknown_email_answers_exactly_like_a_known_one(client, db, register_and_verify):
    register_and_verify("known@example.com")
    known = client.post(FORGOT, json={"email": "known@example.com"})
    unknown = client.post(FORGOT, json={"email": "nobody@example.com"})
    # Same status, same body: the endpoint never says which addresses have accounts
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert db.query(PasswordReset).count() == 1


def test_the_reset_link_sets_a_new_password_and_ends_every_session(client, db, register_and_verify, caplog):
    tokens = register_and_verify("ada@example.com", password=OLD)
    with caplog.at_level(logging.INFO):
        assert client.post(FORGOT, json={"email": "ada@example.com"}).status_code == 202
    token = _token_from_log(caplog)

    # Only the hash is stored, never the token itself
    row = db.query(PasswordReset).one()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in row.token_hash

    response = client.post(RESET, json={"token": token, "password": NEW})
    assert response.status_code == 200, response.text

    assert _login(client, "ada@example.com", OLD).status_code == 401
    assert _login(client, "ada@example.com", NEW).status_code == 200
    # The session that existed before the reset is gone
    stale = client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
    assert stale.status_code == 401


def test_a_reset_link_works_once(client, register_and_verify, caplog):
    register_and_verify("once@example.com")
    with caplog.at_level(logging.INFO):
        client.post(FORGOT, json={"email": "once@example.com"})
    token = _token_from_log(caplog)
    assert client.post(RESET, json={"token": token, "password": NEW}).status_code == 200
    again = client.post(RESET, json={"token": token, "password": "yet-another-pass-789"})
    assert again.status_code == 400
    assert "invalid or expired" in again.json()["detail"].lower()


def test_an_expired_link_is_refused(client, db, register_and_verify, caplog):
    register_and_verify("late@example.com")
    with caplog.at_level(logging.INFO):
        client.post(FORGOT, json={"email": "late@example.com"})
    token = _token_from_log(caplog)
    row = db.query(PasswordReset).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert client.post(RESET, json={"token": token, "password": NEW}).status_code == 400


def test_a_newer_request_cancels_the_older_link(client, register_and_verify, caplog):
    register_and_verify("twice@example.com")
    with caplog.at_level(logging.INFO):
        client.post(FORGOT, json={"email": "twice@example.com"})
    first = _token_from_log(caplog)
    caplog.clear()
    with caplog.at_level(logging.INFO):
        client.post(FORGOT, json={"email": "twice@example.com"})
    second = _token_from_log(caplog)
    assert first != second
    assert client.post(RESET, json={"token": first, "password": NEW}).status_code == 400
    assert client.post(RESET, json={"token": second, "password": NEW}).status_code == 200


def test_a_garbage_token_and_a_short_password_are_refused(client):
    assert client.post(RESET, json={"token": "not-a-real-token", "password": NEW}).status_code == 400
    assert client.post(RESET, json={"token": "anything", "password": "short"}).status_code == 422


def test_an_sso_only_account_gets_no_reset_link(client, db):
    db.add(User(email="sso@example.com", hashed_password=None, is_active=True))
    db.commit()
    assert client.post(FORGOT, json={"email": "sso@example.com"}).status_code == 202
    assert db.query(PasswordReset).count() == 0


def _auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_change_password_needs_the_current_one(client, register_and_verify):
    tokens = register_and_verify("grace@example.com", password=OLD)
    wrong = client.post(CHANGE, json={"current_password": "not-it-at-all", "new_password": NEW}, headers=_auth(tokens))
    assert wrong.status_code == 400
    assert _login(client, "grace@example.com", OLD).status_code == 200


def test_change_password_keeps_this_session_and_ends_the_others(client, register_and_verify):
    tokens = register_and_verify("linus@example.com", password=OLD)
    other = _login(client, "linus@example.com", OLD).json()  # a second device

    response = client.post(CHANGE, json={"current_password": OLD, "new_password": NEW}, headers=_auth(tokens))
    assert response.status_code == 200, response.text
    fresh = response.json()
    assert "access_token" in fresh  # this browser carries on with new tokens

    # Fresh one first: presenting a revoked token is treated as replay and ends every session
    assert client.post(REFRESH, json={"refresh_token": fresh["refresh_token"]}).status_code == 200
    assert client.post(REFRESH, json={"refresh_token": other["refresh_token"]}).status_code == 401
    assert client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert _login(client, "linus@example.com", NEW).status_code == 200


def test_an_sso_only_account_is_told_it_has_no_password(client, db):
    from src.auth.service.auth_service import AuthService

    user = User(email="sso2@example.com", hashed_password=None, is_active=True)
    db.add(user)
    db.commit()
    token = AuthService.create_access_token_for_user(user)
    response = client.post(
        CHANGE,
        json={"current_password": "whatever-it-is", "new_password": NEW},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "no password" in response.json()["detail"].lower()


def test_change_password_requires_sign_in(client):
    assert client.post(CHANGE, json={"current_password": OLD, "new_password": NEW}).status_code == 401
