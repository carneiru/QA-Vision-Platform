"""The import route with a CI service token (ADR-024), and the mass-archive guard (ADR-023)."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.casebook.core.config import settings
from src.casebook.models import Case

URL = "/api/v1/projects/1/cases/import"
ONE = "Feature: A\n  Scenario: one\n    Given x\n"


def service(project_id=1, scope="cases:import", token_type="service"):
    claims = {"sub": "apikey:9", "project_id": project_id, "organization_id": 10, "scope": scope,
              "token_type": token_type, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    return {"Authorization": f"Bearer {jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}"}


def body(*files, **extra):
    return {"files": [{"path": p, "content": c} for p, c in files], **extra}


def feature(*names):
    return "Feature: F\n" + "".join(f"  Scenario: {n}\n    Given {n}\n" for n in names)


@pytest.fixture
def member(project_role):
    project_role("member")


# --- service token ---------------------------------------------------------------------------

def test_a_service_token_imports_without_asking_project_service(client, http, db):
    r = client.post(URL, json=body(("a.feature", ONE)), headers=service())
    assert r.status_code == 200, r.text
    assert db.query(Case).one().created_by == 0
    assert not http.calls  # the respx router saw no request to project-service


def test_a_token_for_another_project_is_404(client, http):
    assert client.post(URL, json=body(("a.feature", ONE)), headers=service(project_id=2)).status_code == 404
    assert not http.calls


@pytest.mark.parametrize("headers", [service(scope="cases:read"), service(scope=None), service(token_type="access")])
def test_a_token_without_the_import_scope_is_401(client, headers):
    assert client.post(URL, json=body(("a.feature", ONE)), headers=headers).status_code == 401


@pytest.mark.parametrize("method, path", [("get", "/api/v1/projects/1/cases"),
                                          ("patch", "/api/v1/projects/1/cases/1"),
                                          ("get", "/api/v1/projects/1/suites")])
def test_the_service_token_opens_no_other_route(client, method, path):
    kwargs = {"json": {"priority": "high"}} if method == "patch" else {}
    assert getattr(client, method)(path, headers=service(), **kwargs).status_code == 401


def test_a_user_token_still_imports(client, auth, member):
    assert client.post(URL, json=body(("a.feature", ONE)), headers=auth()).status_code == 200


def test_ci_updates_are_recorded_as_user_0(client, auth, member, db):
    client.post(URL, json=body(("a.feature", ONE)), headers=auth())
    client.post(URL, json=body(("a.feature", ONE.replace("Given x", "Given y"))), headers=service())
    assert db.query(Case).one().updated_by == 0


# --- mass-archive guard ----------------------------------------------------------------------

def test_a_full_import_archiving_most_cases_is_refused_unless_allowed(client, auth, member, db):
    client.post(URL, json=body(("a.feature", feature("a1", "a2")), ("b.feature", feature("b1"))), headers=auth())
    dry = client.post(f"{URL}?dry_run=true", json=body(("b.feature", feature("b1")), full=True), headers=auth())
    assert dry.json()["summary"]["mass_archive"] is True
    refused = client.post(URL, json=body(("b.feature", feature("b1")), full=True), headers=auth())
    assert refused.status_code == 409
    assert refused.json()["detail"] | {"message": ""} == {"code": "mass_archive", "message": "", "archived": 2, "live": 3}
    assert db.query(Case).filter(Case.status == "archived").count() == 0
    allowed = client.post(URL, json=body(("b.feature", feature("b1")), full=True, allow_mass_archive=True), headers=auth())
    assert allowed.status_code == 200 and allowed.json()["summary"]["archived"] == 2


def test_archiving_exactly_half_is_not_a_mass_archive(client, auth, member):
    client.post(URL, json=body(("a.feature", feature("a1", "a2")), ("b.feature", feature("b1", "b2"))), headers=auth())
    r = client.post(URL, json=body(("b.feature", feature("b1", "b2")), full=True), headers=auth())
    assert r.status_code == 200 and r.json()["summary"]["archived"] == 2
    assert r.json()["summary"]["mass_archive"] is False


def test_without_full_there_is_no_mass_archive(client, auth, member):
    client.post(URL, json=body(("a.feature", feature("a1", "a2", "a3"))), headers=auth())
    r = client.post(URL, json=body(("a.feature", feature("a1"))), headers=auth())
    assert r.status_code == 200 and r.json()["summary"]["archived"] == 2
    assert r.json()["summary"]["mass_archive"] is False


def test_a_first_full_import_is_never_a_mass_archive(client, auth, member):
    r = client.post(URL, json=body(("a.feature", ONE), full=True), headers=auth())
    assert r.status_code == 200 and r.json()["summary"]["mass_archive"] is False


# --- user-style tokens that are not access tokens --------------------------------------------

@pytest.mark.parametrize("claims", [{"purpose": "mfa"}, {"purpose": "password_reset"}, {"token_type": "refresh"}])
def test_a_user_style_token_with_purpose_is_401_on_import(client, http, claims):
    claims_all = {"sub": "5", "exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    headers = {"Authorization": f"Bearer {jwt.encode(claims_all, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}"}
    assert client.post(URL, json=body(("a.feature", ONE)), headers=headers).status_code == 401
    assert not http.calls
