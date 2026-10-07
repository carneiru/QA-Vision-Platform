"""GET/PUT/DELETE /ci-target. GitHub is stubbed (the `github` fixture); the token never comes back."""
import logging
from datetime import datetime, timezone

import pytest

from src.casebook.models import CiTarget, CiTargetEvent, RunRequest

URL = "/api/v1/projects/1/ci-target"
TOKEN = "github_pat_11AAAAAAA0" + "b" * 30 + "a1b2"
BODY = {"repo": "acme/obt", "workflow": "qa-vision-run.yml", "ref": "main", "token": TOKEN}
NOT_CONFIGURED = "Running tests from QA Vision is not configured on this server"


@pytest.fixture
def owner(project_role, secrets_key):
    project_role("owner")


def put(client, auth, **changes):
    return client.put(URL, json={**BODY, **changes}, headers=auth())


def github_calls(http):
    return [c for c in http.calls if c.request.url.host == "api.github.com"]


def test_save_checks_github_stores_ciphertext_and_shows_last4_only(client, auth, owner, github, db, caplog):
    caplog.set_level(logging.DEBUG)
    github.check()
    r = put(client, auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True and body["configured"] is True
    assert (body["repo"], body["workflow"], body["ref"], body["token_last4"]) == ("acme/obt", "qa-vision-run.yml", "main", "a1b2")
    assert body["token_expires_at"].startswith("2027-03-12")
    assert body["last_change"]["action"] == "created" and body["last_change"]["user_id"] == 1
    assert TOKEN not in r.text and TOKEN not in client.get(URL, headers=auth()).text
    assert TOKEN not in db.get(CiTarget, 1).token_encrypted
    assert TOKEN not in caplog.text


def test_a_token_without_expiry_stores_null(client, auth, owner, github):
    github.check(expires=None)
    assert put(client, auth).json()["token_expires_at"] is None


@pytest.mark.parametrize("status, message", [
    (401, "token invalid or expired"),
    (403, "token has no Actions access to this repository"),
    (404, "repository or workflow not found. The workflow file must exist on the repository's default branch")])
def test_github_refusals_are_422_with_a_specific_message(client, auth, owner, github, db, status, message):
    github.check(status=status)
    r = put(client, auth)
    assert r.status_code == 422 and r.json()["detail"] == message
    assert db.get(CiTarget, 1) is None and db.query(CiTargetEvent).count() == 0


def test_a_rate_limit_is_503_with_retry_after_and_stores_nothing(client, auth, owner, github, db):
    github.check(status=429, headers={"retry-after": "30"})
    r = put(client, auth)
    assert r.status_code == 503 and r.json()["detail"] == "GitHub rate limit, try again in 30 s"
    assert r.headers["retry-after"] == "30" and db.get(CiTarget, 1) is None


@pytest.mark.parametrize("changes", [
    {"repo": "acme"}, {"repo": "acme/obt/x"}, {"repo": "acme/.."}, {"repo": "a b/c"},
    {"workflow": "run.json"}, {"workflow": "../run.yml"},
    {"ref": "-x"}, {"ref": "a..b"}, {"ref": "a\x00b"}, {"ref": "x" * 256}])
def test_bad_names_are_422_before_github_is_asked(client, auth, owner, http, changes):
    assert put(client, auth, **changes).status_code == 422
    assert not github_calls(http)


def test_a_pasted_token_with_whitespace_is_trimmed(client, auth, owner, github):
    workflow_route = github.check()
    r = put(client, auth, token=f"  {TOKEN}\r\n")
    assert r.status_code == 200, r.text
    assert r.json()["token_last4"] == "a1b2"
    assert workflow_route.calls.last.request.headers["Authorization"] == f"Bearer {TOKEN}"


def test_a_malformed_token_is_422_and_not_echoed(client, auth, owner, http):
    bad = TOKEN + "!"
    r = put(client, auth, token=bad)
    assert r.status_code == 422
    assert bad not in r.text and TOKEN not in r.text
    assert not github_calls(http)


def test_the_first_save_needs_a_token(client, auth, owner, github):
    github.check()
    r = client.put(URL, json={"repo": "acme/obt"}, headers=auth())
    assert r.status_code == 422 and "token" in r.json()["detail"]


def test_events_for_create_update_token_replacement_and_delete(client, auth, owner, github, db):
    github.check()
    assert put(client, auth).status_code == 200
    updated = client.put(URL, json={"repo": "acme/obt", "ref": "release"}, headers=auth())  # keeps the stored token
    assert updated.status_code == 200 and updated.json()["ref"] == "release" and updated.json()["token_last4"] == "a1b2"
    assert put(client, auth, token="github_pat_" + "c" * 30 + "zzzz").json()["token_last4"] == "zzzz"
    assert client.delete(URL, headers=auth()).status_code == 204
    assert [e.action for e in db.query(CiTargetEvent).order_by(CiTargetEvent.id)] == [
        "created", "updated", "token_replaced", "deleted"]
    after = client.get(URL, headers=auth()).json()
    assert after["configured"] is False and after["repo"] is None and after["last_change"]["action"] == "deleted"


@pytest.mark.parametrize("role", ["member", "viewer", "billing_manager"])
def test_only_owners_and_admins_change_it_but_every_role_reads(client, auth, project_role, secrets_key, github, role):
    project_role(role)
    github.check()
    assert put(client, auth).status_code == 403
    assert client.delete(URL, headers=auth()).status_code == 403
    assert client.get(URL, headers=auth()).status_code == 200


def test_an_admin_may_save_and_disconnect(client, auth, project_role, secrets_key, github):
    project_role("admin")
    github.check()
    assert put(client, auth).status_code == 200
    assert client.delete(URL, headers=auth()).status_code == 204


def test_without_a_secrets_key_get_says_unavailable_and_put_is_503(client, auth, project_role, no_secrets_key, http):
    project_role("owner")
    assert client.get(URL, headers=auth()).json()["available"] is False
    r = put(client, auth)
    assert r.status_code == 503 and r.json()["detail"] == NOT_CONFIGURED
    assert TOKEN not in r.text and not github_calls(http)


def test_delete_without_a_target_is_404(client, auth, owner):
    assert client.delete(URL, headers=auth()).status_code == 404


def test_delete_is_409_while_a_run_is_active(client, auth, owner, github, db):
    github.check()
    put(client, auth)
    db.add(RunRequest(project_id=1, requested_by=1, requested_at=datetime.now(timezone.utc), selection=[], status="running"))
    db.commit()
    assert client.delete(URL, headers=auth()).status_code == 409
    assert db.get(CiTarget, 1) is not None


def test_a_422_never_echoes_the_body_so_a_valid_token_without_repo_stays_secret(client, auth, owner, http):
    r = client.put(URL, json={"token": TOKEN}, headers=auth())
    assert r.status_code == 422
    assert TOKEN not in r.text and "input" not in r.text
    assert not github_calls(http)
