"""Cross-user isolation.

`UserService.get_user_by_id` once read `filter(user_id == user_id)` -- a Python tautology,
so SQLAlchemy emitted `WHERE true` and returned the first row in `users` for every id. That
made /auth/refresh-token hand out an access token for users.id == 1, and PUT /users/me
overwrite that account. The pre-existing suite could not see it because every test used a
single-user database.
"""

def _login(client, email):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword123"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_refresh_returns_a_token_for_the_same_user(client, register_and_verify):
    register_and_verify("first@example.com", full_name="first@example.com")
    register_and_verify("second@example.com", full_name="second@example.com")
    second = _login(client, "second@example.com")

    refreshed = client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": second["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text

    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "second@example.com", "refresh must not switch identity"


def test_updating_me_does_not_touch_another_user(client, register_and_verify):
    register_and_verify("first@example.com", full_name="first@example.com")
    register_and_verify("second@example.com", full_name="second@example.com")
    second = _login(client, "second@example.com")

    updated = client.put(
        "/api/v1/users/me",
        json={"full_name": "Renamed By Second"},
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["email"] == "second@example.com"

    # the first account must be untouched, and must still be able to log in
    still_first = _login(client, "first@example.com")
    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {still_first['access_token']}"},
    )
    assert me.json()["email"] == "first@example.com"
    assert me.json()["full_name"] == "first@example.com"


def test_user_responses_never_include_password_hashes(client, register_and_verify):
    register_and_verify("first@example.com")
    tokens = _login(client, "first@example.com")

    me = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert "hashed_password" not in me.json()


def test_user_cannot_promote_themselves_to_superuser(client, register_and_verify):
    """PUT /users/me accepted the full UserUpdate and setattr'd whatever arrived, so any
    user could send {"is_superuser": true} and then read /users/."""
    register_and_verify("first@example.com")
    register_and_verify("second@example.com")
    second = _login(client, "second@example.com")
    auth = {"Authorization": f"Bearer {second['access_token']}"}

    assert client.get("/api/v1/users/", headers=auth).status_code == 403

    response = client.put(
        "/api/v1/users/me", json={"is_superuser": True, "full_name": "Sneaky"}, headers=auth
    )
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        assert response.json().get("is_superuser") is not True

    assert client.get("/api/v1/users/", headers=auth).status_code == 403, (
        "self-update must not grant superuser"
    )


def test_user_cannot_deactivate_another_account_via_self_update(client, register_and_verify):
    """is_active is equally privileged -- flipping it is a self-inflicted lockout at best
    and a tampering vector at worst."""
    register_and_verify("first@example.com")
    first = _login(client, "first@example.com")
    auth = {"Authorization": f"Bearer {first['access_token']}"}

    response = client.put("/api/v1/users/me", json={"is_active": False}, headers=auth)
    assert response.status_code in (200, 422)

    assert _login(client, "first@example.com")["access_token"]


def test_logout_cannot_revoke_another_users_session(client, register_and_verify):
    register_and_verify("first@example.com")
    register_and_verify("second@example.com")
    first = _login(client, "first@example.com")
    second = _login(client, "second@example.com")

    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": first["refresh_token"]},
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert response.status_code != 200

    refreshed = client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": first["refresh_token"]}
    )
    assert refreshed.status_code == 200


def test_password_change_requires_the_current_password(client, register_and_verify):
    """A stolen access token is a bearer credential with a multi-day life. Without this
    check, a minute's use of one is enough to replace the password and own the account."""
    register_and_verify("first@example.com")
    first = _login(client, "first@example.com")
    auth = {"Authorization": f"Bearer {first['access_token']}"}

    refused = client.put(
        "/api/v1/users/me", json={"password": "attackerchosen1"}, headers=auth
    )
    assert refused.status_code == 400, refused.text

    wrong = client.put(
        "/api/v1/users/me",
        json={"password": "attackerchosen1", "current_password": "notmypassword"},
        headers=auth,
    )
    assert wrong.status_code == 400, wrong.text

    assert _login(client, "first@example.com")["access_token"]


def test_password_change_revokes_existing_sessions(client, register_and_verify):
    register_and_verify("first@example.com")
    first = _login(client, "first@example.com")
    stolen_refresh = first["refresh_token"]

    changed = client.put(
        "/api/v1/users/me",
        json={"password": "brandnewpassword1", "current_password": "securepassword123"},
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert changed.status_code == 200, changed.text

    reused = client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": stolen_refresh}
    )
    assert reused.status_code == 401, "sessions must not outlive the password they were issued under"


def test_short_password_is_refused_on_self_update(client, register_and_verify):
    register_and_verify("first@example.com")
    first = _login(client, "first@example.com")

    response = client.put(
        "/api/v1/users/me",
        json={"password": "x", "current_password": "securepassword123"},
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert response.status_code == 422, response.text


def test_null_password_is_a_client_error_not_a_crash(client, register_and_verify):
    """`password` is Optional, so an explicit null passed validation and reached
    get_password_hash(None), which raises."""
    register_and_verify("first@example.com")
    first = _login(client, "first@example.com")

    response = client.put(
        "/api/v1/users/me",
        json={"password": None, "current_password": "securepassword123"},
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert response.status_code == 400, response.text

    assert _login(client, "first@example.com")["access_token"]


def test_registration_rejects_privileged_fields_in_the_body(client):
    """An earlier version of this asserted the field was *ignored*, which passed against the
    code it was written to guard -- Pydantic silently drops unknown fields, so a 200 proved
    nothing. Input schemas now reject them, which is a difference a test can see."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "sneaky@example.com",
            "password": "securepassword123",
            "is_superuser": True,
        },
    )
    assert response.status_code == 422, response.text

    assert client.post(
        "/api/v1/auth/login",
        json={"email": "sneaky@example.com", "password": "securepassword123"},
    ).status_code == 401, "the account must not have been created"


def test_self_update_cannot_change_email(client, register_and_verify):
    """Changing an address needed no password and no proof of owning the new one, so any
    authenticated user could take any unregistered address in a single request. Its real
    owner is then locked out permanently: registration answers 400, Google SSO answers 409."""
    attacker = register_and_verify("attacker@example.com")

    response = client.put(
        "/api/v1/users/me",
        json={"email": "ceo@example.com"},
        headers={"Authorization": f"Bearer {attacker['access_token']}"},
    )
    assert response.status_code == 422, response.text

    # the address is still free for its real owner -- registration now only begins the
    # flow, so 202 proves the address is unclaimed, not that a full account was made
    claimed = client.post(
        "/api/v1/auth/register",
        json={"email": "ceo@example.com", "password": "securepassword123"},
    )
    assert claimed.status_code == 202, claimed.text


def test_replaying_a_rotated_refresh_token_ends_every_session(client, register_and_verify):
    """Rotation alone does not survive theft: the thief rotates the stolen token and it is
    the owner's next refresh that fails, leaving the thief's chain live. A replay is treated
    as a compromised chain instead."""
    first = register_and_verify("first@example.com")
    stolen = first["refresh_token"]

    thief = client.post("/api/v1/auth/refresh-token", json={"refresh_token": stolen})
    assert thief.status_code == 200
    thief_chain = thief.json()["refresh_token"]

    replay = client.post("/api/v1/auth/refresh-token", json={"refresh_token": stolen})
    assert replay.status_code == 401

    assert client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": thief_chain}
    ).status_code == 401, "a replay must revoke every session, the thief's included"


def test_non_superuser_reading_another_id_is_forbidden_not_a_bad_request(client, register_and_verify):
    """Answered before the id is looked up, so a non-superuser cannot probe which ids exist;
    and 403 rather than the 400 this used to return."""
    first = register_and_verify("first@example.com")

    response = client.get(
        "/api/v1/users/999999",
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert response.status_code == 403, response.text
