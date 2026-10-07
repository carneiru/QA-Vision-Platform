"""POST/GET run-requests: Play dispatches the CI workflow; GETs refresh from GitHub (stubbed)."""
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.casebook.models import Case, CiTarget, RunRequest, Suite, SuiteCase
from src.casebook.service import run_request_service
from src.casebook.utils import secret_box

BASE = "/api/v1/projects/1"
URL = f"{BASE}/run-requests"
TOKEN = "github_pat_" + "d" * 40
CHECKOUT, LOGIN = "tests/features/checkout.feature", "tests/features/login.feature"
VOUCHER_NAME = 'Pay with a "voucher" (50% off) $5 [promo]'
FEATURE = (
    "Feature: Checkout\n"
    "  Scenario: Pay by card\n    Given x\n"
    f"  Scenario: {VOUCHER_NAME}\n    Given y\n"
    "  Scenario Outline: Book <city> flight\n    Given <city>\n    Examples:\n      | city |\n      | Rome |\n"
)
# The import numbers cases in (path, scenario) order; the manual case comes last
BOOK, CARD, VOUCHER, LOG_IN, MANUAL = 1, 2, 3, 4, 5


class Clock:
    def __init__(self):
        self.at = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.at

    def tick(self, **delta):
        self.at += timedelta(**delta)


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(run_request_service, "now", c)
    return c


@pytest.fixture
def project(client, auth, project_role, secrets_key, db, github):
    project_role("member")
    files = [{"path": CHECKOUT, "content": FEATURE},
             {"path": LOGIN, "content": "Feature: Login\n  Scenario: Log in\n    Given z\n"}]
    assert client.post(f"{BASE}/cases/import", json={"files": files}, headers=auth()).status_code == 200
    assert client.post(f"{BASE}/cases", json={"title": "Manual"}, headers=auth()).status_code == 201
    assert {c.number: c.scenario_name for c in db.query(Case)} == {
        BOOK: "Book <city> flight", CARD: "Pay by card", VOUCHER: VOUCHER_NAME, LOG_IN: "Log in", MANUAL: None}
    db.add(CiTarget(project_id=1, provider="github", repo=github.repo, workflow=github.workflow, ref="main",
                    token_encrypted=secret_box.encrypt(TOKEN), token_last4=TOKEN[-4:], updated_by=1,
                    updated_at=datetime.now(timezone.utc)))
    db.commit()
    return client


def play(client, auth, **body):
    return client.post(URL, json=body, headers=auth())


def get(client, auth, rid):
    r = client.get(f"{URL}/{rid}", headers=auth())
    assert r.status_code == 200, r.text
    return r.json()


def test_cases_become_files_and_raw_names_and_the_dispatch_body_is_exact(project, auth, github, clock):
    route = github.dispatch(run_id=500)
    r = play(project, auth, case_numbers=[CARD, BOOK, LOG_IN, CARD])
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["status"], body["case_count"], body["refreshing"], body["requested_by"]) == ("queued", 3, True, 1)
    assert body["selection"][0] == {"case_number": CARD, "path": CHECKOUT, "name": "Pay by card"}
    assert json.loads(route.calls.last.request.read()) == {
        "ref": "main",
        "inputs": {
            "paths": json.dumps([CHECKOUT, LOGIN]),
            "names": json.dumps(["Pay by card", "Book <city> flight", "Log in"]),
            "request_id": str(body["id"]),
        },
        "return_run_details": True,
    }
    assert TOKEN not in r.text


def test_a_200_dispatch_stores_the_run_at_once_and_polling_never_lists_runs(project, auth, github, http, clock):
    github.dispatch(run_id=501)
    body = play(project, auth, case_numbers=[CARD]).json()
    assert (body["status"], body["github_run_id"], body["github_run_url"]) == (
        "queued", 501, f"https://github.com/{github.repo}/actions/runs/501")
    run = github.run(github.run_body(501, body["id"], status="in_progress"))
    clock.tick(minutes=3)  # well past the 2-minute fallback limit: a known run never becomes failed_to_start
    assert get(project, auth, body["id"])["status"] == "running"
    assert run.call_count == 1
    assert not [c for c in http.calls if c.request.url.path.endswith(f"/workflows/{github.workflow}/runs")]


def test_a_dispatch_url_outside_github_is_not_stored(project, auth, github, http, clock):
    http.post(f"https://api.github.com/repos/{github.repo}/actions/workflows/{github.workflow}/dispatches",
              name="gh-dispatch").mock(
        return_value=httpx.Response(200, json={"workflow_run_id": 501, "html_url": "javascript:alert(1)"}))
    body = play(project, auth, case_numbers=[CARD]).json()
    assert body["github_run_id"] == 501 and body["github_run_url"] is None


def test_a_name_with_quotes_and_regex_characters_is_sent_raw(project, auth, github, clock):
    route = github.dispatch()
    assert play(project, auth, case_numbers=[VOUCHER]).status_code == 201
    assert json.loads(json.loads(route.calls.last.request.read())["inputs"]["names"]) == [VOUCHER_NAME]


def test_a_suite_expands_in_its_order(project, auth, db, github, clock):
    suite = Suite(project_id=1, name="Smoke", created_by=1)
    db.add(suite)
    db.commit()
    ids = {c.number: c.id for c in db.query(Case)}
    db.add_all([SuiteCase(suite_id=suite.id, case_id=ids[LOG_IN], position=0),
                SuiteCase(suite_id=suite.id, case_id=ids[CARD], position=1)])
    db.commit()
    github.dispatch()
    r = play(project, auth, suite_id=suite.id)
    assert r.status_code == 201, r.text
    assert r.json()["suite_id"] == suite.id
    assert [c["case_number"] for c in r.json()["selection"]] == [LOG_IN, CARD]


def test_an_empty_suite_is_422_and_an_unknown_one_404(project, auth, db, github):
    suite = Suite(project_id=1, name="Empty", created_by=1)
    db.add(suite)
    db.commit()
    dispatch = github.dispatch()
    assert play(project, auth, suite_id=suite.id).status_code == 422
    assert play(project, auth, suite_id=999).status_code == 404
    assert not dispatch.called


def test_manual_archived_and_unknown_cases_are_rejected_with_their_numbers(project, auth, db, github):
    db.query(Case).filter(Case.number == BOOK).one().status = "archived"
    db.commit()
    dispatch = github.dispatch()
    r = play(project, auth, case_numbers=[BOOK, CARD, MANUAL, 99])
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "TC-99" in detail and "TC-5" in detail and "TC-1" in detail and "TC-2" not in detail
    assert not dispatch.called


def test_a_case_without_scenario_name_asks_for_a_reimport(project, auth, db, github):
    db.query(Case).filter(Case.number == CARD).one().scenario_name = None
    db.commit()
    r = play(project, auth, case_numbers=[CARD])
    assert r.status_code == 422
    assert "re-import the .feature files first" in r.json()["detail"] and "TC-2" in r.json()["detail"]


@pytest.mark.parametrize("body", [
    {"case_numbers": []}, {"case_numbers": list(range(1, 202))}, {}, {"case_numbers": [1], "suite_id": 1},
    {"case_numbers": [0]}])
def test_bad_bodies_are_422(project, auth, body):
    assert project.post(URL, json=body, headers=auth()).status_code == 422


def test_a_selection_too_large_for_one_dispatch_is_422(project, auth, github):
    big = "Feature: Big\n" + "".join(f"  Scenario: {'x' * 330} {i}\n    Given x\n" for i in range(200))
    imported = project.post(f"{BASE}/cases/import", json={"files": [{"path": "tests/features/big.feature", "content": big}]},
                            headers=auth())
    assert imported.status_code == 200
    dispatch = github.dispatch()
    r = play(project, auth, case_numbers=list(range(6, 206)))
    assert r.status_code == 422 and "too large" in r.json()["detail"]
    assert not dispatch.called


def test_a_viewer_is_403(project, auth, project_role):
    project_role("viewer")
    assert play(project, auth, case_numbers=[CARD]).status_code == 403
    assert project.get(URL, headers=auth()).status_code == 200


def test_no_target_is_412(project, auth, db):
    db.query(CiTarget).delete()
    db.commit()
    assert play(project, auth, case_numbers=[CARD]).status_code == 412


def test_a_failed_dispatch_is_failed_to_start_and_frees_the_slot(project, auth, github, clock):
    github.dispatch(status=404)
    r = play(project, auth, case_numbers=[CARD])
    assert r.status_code == 201
    assert r.json()["status"] == "failed_to_start" and "default branch" in r.json()["error"]
    assert r.json()["refreshing"] is False
    github.dispatch()
    assert play(project, auth, case_numbers=[CARD]).status_code == 201


def test_a_rate_limited_dispatch_leaves_nothing_behind(project, auth, github, db, clock):
    github.dispatch(status=429, headers={"retry-after": "30"})
    r = play(project, auth, case_numbers=[CARD])
    assert r.status_code == 503 and r.json()["detail"] == "GitHub rate limit, try again in 30 s"
    assert db.query(RunRequest).count() == 0


def test_an_active_run_still_running_on_github_is_409(project, auth, github, clock):
    github.dispatch(run_id=500)
    first = play(project, auth, case_numbers=[CARD]).json()
    github.run(github.run_body(500, first["id"], status="in_progress"))
    r = play(project, auth, case_numbers=[BOOK])
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "run_active" and r.json()["detail"]["run_request_id"] == first["id"]


def test_a_run_that_finished_unseen_does_not_block_the_next_play(project, auth, github, clock):
    github.dispatch(run_id=500)
    first = play(project, auth, case_numbers=[CARD]).json()
    github.run(github.run_body(500, first["id"], status="completed", conclusion="success"))
    github.dispatch(run_id=600)
    second = play(project, auth, case_numbers=[BOOK])  # inside the 5 s throttle: the pre-409 refresh ignores it
    assert second.status_code == 201, second.text
    assert get(project, auth, first["id"])["status"] == "completed"


def test_double_click_dispatches_once(project, auth, github, clock):
    dispatch = github.dispatch(run_id=500)
    github.run(github.run_body(500, 1, status="queued"))  # the pre-409 refresh asks for that run: still queued
    a = play(project, auth, case_numbers=[CARD])
    b = play(project, auth, case_numbers=[CARD])
    assert (a.status_code, b.status_code) == (201, 409)
    assert dispatch.call_count == 1


@pytest.mark.parametrize("gh_status, conclusion, status", [
    ("queued", None, "queued"), ("waiting", None, "queued"), ("requested", None, "queued"),
    ("pending", None, "queued"), ("in_progress", None, "running"), ("completed", "success", "completed"),
    ("completed", "failure", "completed"), ("completed", "timed_out", "completed"),
    ("completed", "cancelled", "cancelled")])
def test_github_status_maps_to_ours(project, auth, github, clock, gh_status, conclusion, status):
    github.dispatch(run_id=501)
    rid = play(project, auth, case_numbers=[CARD]).json()["id"]
    github.run(github.run_body(501, rid, status=gh_status, conclusion=conclusion))
    clock.tick(seconds=6)
    body = get(project, auth, rid)
    assert (body["status"], body["conclusion"]) == (status, conclusion)
    assert body["refreshing"] is (status in ("queued", "running"))


# --- The 204 fallback: GitHub gave no run details, so polling matches the run by its title ---

def test_after_a_204_the_run_is_matched_by_display_title(project, auth, github, clock):
    github.dispatch()  # 204: no run details
    started = play(project, auth, case_numbers=[CARD]).json()
    rid = started["id"]
    assert started["github_run_id"] is None and started["github_run_url"] is None
    github.runs(github.run_body(400, rid + 1), github.run_body(501, rid))
    clock.tick(seconds=6)
    matched = get(project, auth, rid)
    assert (matched["status"], matched["github_run_id"]) == ("queued", 501)
    assert matched["github_run_url"] == f"https://github.com/{github.repo}/actions/runs/501"
    github.run(github.run_body(501, rid, status="in_progress"))
    clock.tick(seconds=6)
    assert get(project, auth, rid)["status"] == "running"


def test_a_run_url_outside_github_is_not_stored(project, auth, github, clock):
    github.dispatch()
    rid = play(project, auth, case_numbers=[CARD]).json()["id"]
    github.runs({**github.run_body(501, rid), "html_url": "javascript:alert(1)"})
    clock.tick(seconds=6)
    body = get(project, auth, rid)
    assert body["github_run_id"] == 501 and body["github_run_url"] is None


def test_github_is_asked_at_most_every_5_seconds(project, auth, github, clock):
    github.dispatch()
    rid = play(project, auth, case_numbers=[CARD]).json()["id"]
    runs = github.runs()
    clock.tick(seconds=6)
    get(project, auth, rid)
    clock.tick(seconds=3)
    get(project, auth, rid)
    project.get(URL, headers=auth())
    assert runs.call_count == 1
    clock.tick(seconds=3)
    get(project, auth, rid)
    assert runs.call_count == 2


def test_the_run_list_is_asked_from_a_minute_before_the_request_in_utc(project, auth, github, clock):
    github.dispatch()
    rid = play(project, auth, case_numbers=[CARD]).json()["id"]
    runs = github.runs()
    clock.tick(seconds=6)
    get(project, auth, rid)
    params = runs.calls.last.request.url.params
    assert params["created"] == ">=2026-10-07T09:59:00Z" and params["event"] == "workflow_dispatch"


def test_a_run_never_seen_after_2_minutes_failed_to_start(project, auth, github, clock):
    github.dispatch()
    rid = play(project, auth, case_numbers=[CARD]).json()["id"]
    github.runs()
    clock.tick(seconds=119)
    assert get(project, auth, rid)["status"] == "queued"
    clock.tick(seconds=6)
    body = get(project, auth, rid)
    assert (body["status"], body["error"], body["refreshing"]) == ("failed_to_start", "The workflow did not start", False)
    assert play(project, auth, case_numbers=[BOOK]).status_code == 201


def test_a_github_outage_during_refresh_changes_nothing(project, auth, github, http, clock):
    github.dispatch()
    rid = play(project, auth, case_numbers=[CARD]).json()["id"]
    http.get(f"https://api.github.com/repos/{github.repo}/actions/workflows/{github.workflow}/runs",
             name="gh-runs").mock(return_value=httpx.Response(503))
    clock.tick(minutes=3)
    body = get(project, auth, rid)
    assert body["status"] == "queued" and body["error"] is None


def test_the_list_is_newest_first_with_a_total(project, auth, github, clock):
    github.dispatch(status=404)
    first = play(project, auth, case_numbers=[CARD]).json()  # failed_to_start frees the slot
    github.dispatch()
    second = play(project, auth, case_numbers=[LOG_IN]).json()
    github.runs()
    page = project.get(f"{URL}?limit=1", headers=auth()).json()
    assert page["total"] == 2 and [i["id"] for i in page["items"]] == [second["id"]]
    assert project.get(f"{URL}?limit=1&offset=1", headers=auth()).json()["items"][0]["id"] == first["id"]


def test_another_projects_request_is_404(project, auth, github, project_role, clock):
    github.dispatch()
    rid = play(project, auth, case_numbers=[CARD]).json()["id"]
    project_role("member", project_id=2)
    assert project.get(f"/api/v1/projects/2/run-requests/{rid}", headers=auth()).status_code == 404


# --- Controller ruling F1: a run GitHub no longer knows ends the row; other failures keep the state ---

def test_a_known_run_gone_from_github_ends_cancelled_and_frees_the_slot(project, auth, github, http, clock):
    github.dispatch(run_id=501)
    rid = play(project, auth, case_numbers=[CARD]).json()["id"]
    http.get(f"https://api.github.com/repos/{github.repo}/actions/runs/501", name="gh-run-501").mock(
        return_value=httpx.Response(404))
    clock.tick(seconds=6)
    body = get(project, auth, rid)
    assert (body["status"], body["error"], body["refreshing"]) == ("cancelled", "The run is no longer on GitHub", False)
    github.dispatch(run_id=502)
    assert play(project, auth, case_numbers=[BOOK]).status_code == 201


@pytest.mark.parametrize("code", [401, 403, 500, 503])
def test_other_github_failures_for_a_known_run_keep_the_status_and_store_the_error(
        project, auth, github, http, clock, code):
    github.dispatch(run_id=501)
    rid = play(project, auth, case_numbers=[CARD]).json()["id"]
    http.get(f"https://api.github.com/repos/{github.repo}/actions/runs/501", name="gh-run-501").mock(
        return_value=httpx.Response(code))
    clock.tick(seconds=6)
    body = get(project, auth, rid)
    assert body["status"] == "queued" and body["refreshing"] is True and body["error"]


def test_a_github_failure_that_clears_removes_the_stored_error(project, auth, github, http, clock):
    github.dispatch(run_id=501)
    rid = play(project, auth, case_numbers=[CARD]).json()["id"]
    http.get(f"https://api.github.com/repos/{github.repo}/actions/runs/501", name="gh-run-501").mock(
        return_value=httpx.Response(500))
    clock.tick(seconds=6)
    assert get(project, auth, rid)["error"]
    github.run(github.run_body(501, rid, status="in_progress"))
    clock.tick(seconds=6)
    body = get(project, auth, rid)
    assert (body["status"], body["error"]) == ("running", None)
