"""Cross-user isolation.

`UserService.get_user_by_id` once read `filter(user_id == user_id)` -- a Python tautology,
so SQLAlchemy emitted `WHERE true` and returned the first row in `users` for every id. That
made /auth/refresh-token hand out an access token for users.id == 1, and PUT /users/me
overwrite that account. The pre-existing suite could not see it because every test used a
single-user database.
"""

def _register(client, email):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepassword123", "full_name": email},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _login(client, email):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword123"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_refresh_returns_a_token_for_the_same_user(client):
    _register(client, "first@example.com")
    _register(client, "second@example.com")
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


def test_updating_me_does_not_touch_another_user(client):
    first = _register(client, "first@example.com")
    _register(client, "second@example.com")
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
    assert me.json()["full_name"] == first["full_name"]


def test_user_responses_never_include_password_hashes(client):
    _register(client, "first@example.com")
    tokens = _login(client, "first@example.com")

    me = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert "hashed_password" not in me.json()


def test_user_cannot_promote_themselves_to_superuser(client):
    """PUT /users/me accepted the full UserUpdate and setattr'd whatever arrived, so any
    user could send {"is_superuser": true} and then read /users/."""
    _register(client, "first@example.com")
    _register(client, "second@example.com")
    second = _login(client, "second@example.com")
    auth = {"Authorization": f"Bearer {second['access_token']}"}

    # listing users is superuser-only, and must stay that way
    assert client.get("/api/v1/users/", headers=auth).status_code == 403

    response = client.put(
        "/api/v1/users/me", json={"is_superuser": True, "full_name": "Sneaky"}, headers=auth
    )
    # the request may be accepted, but the privileged field must not take effect
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        assert response.json().get("is_superuser") is not True

    assert client.get("/api/v1/users/", headers=auth).status_code == 403, (
        "self-update must not grant superuser"
    )


def test_user_cannot_deactivate_another_account_via_self_update(client):
    """is_active is equally privileged -- flipping it is a self-inflicted lockout at best
    and a tampering vector at worst."""
    _register(client, "first@example.com")
    first = _login(client, "first@example.com")
    auth = {"Authorization": f"Bearer {first['access_token']}"}

    response = client.put("/api/v1/users/me", json={"is_active": False}, headers=auth)
    assert response.status_code in (200, 422)

    # still active: able to log in again
    assert _login(client, "first@example.com")["access_token"]


def test_logout_cannot_revoke_another_users_session(client):
    _register(client, "first@example.com")
    _register(client, "second@example.com")
    first = _login(client, "first@example.com")
    second = _login(client, "second@example.com")

    # second tries to revoke first's refresh token
    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": first["refresh_token"]},
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert response.status_code != 200

    # first's session still works
    refreshed = client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": first["refresh_token"]}
    )
    assert refreshed.status_code == 200


def test_password_change_requires_the_current_password(client):
    """A stolen access token is a bearer credential with a multi-day life. Without this
    check, a minute's use of one is enough to replace the password and own the account."""
    _register(client, "first@example.com")
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

    # the original password still works
    assert _login(client, "first@example.com")["access_token"]


def test_password_change_revokes_existing_sessions(client):
    _register(client, "first@example.com")
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


def test_short_password_is_refused_on_self_update(client):
    _register(client, "first@example.com")
    first = _login(client, "first@example.com")

    response = client.put(
        "/api/v1/users/me",
        json={"password": "x", "current_password": "securepassword123"},
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert response.status_code == 422, response.text


def test_changing_email_to_a_taken_address_is_a_client_error(client):
    """The UNIQUE constraint surfaced as an uncaught IntegrityError, so this was a 500."""
    _register(client, "first@example.com")
    _register(client, "second@example.com")
    second = _login(client, "second@example.com")

    response = client.put(
        "/api/v1/users/me",
        json={"email": "first@example.com"},
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert response.status_code == 400, response.text


def test_registration_ignores_privileged_fields_in_the_body(client):
    """UserBase carried is_superuser, so /auth/register accepted it. Nothing copied it into
    the model, which made this a trap rather than a hole -- one line away from being an
    escalation at signup."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "sneaky@example.com",
            "password": "securepassword123",
            "is_superuser": True,
            "is_active": True,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_superuser"] is False

    tokens = _login(client, "sneaky@example.com")
    listing = client.get(
        "/api/v1/users/", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert listing.status_code == 403


def test_null_password_is_a_client_error_not_a_crash(client):
    """`password` is Optional, so an explicit null passed validation and reached
    get_password_hash(None), which raises."""
    _register(client, "first@example.com")
    first = _login(client, "first@example.com")

    response = client.put(
        "/api/v1/users/me",
        json={"password": None, "current_password": "securepassword123"},
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert response.status_code == 400, response.text

    # the account is unchanged and still usable
    assert _login(client, "first@example.com")["access_token"]
