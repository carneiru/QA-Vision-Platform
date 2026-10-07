"""The GitHub REST client: api.github.com only, no redirects, specific messages, no token in errors."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.casebook.utils import github_client as gh

TOKEN = "github_pat_" + "a" * 40


def test_check_sends_the_api_headers_and_returns_the_expiry(github):
    route = github.check()
    assert gh.check_target(TOKEN, github.repo, github.workflow) == datetime(2027, 3, 12, tzinfo=timezone.utc)
    sent = route.calls.last.request
    assert sent.url.host == "api.github.com"
    assert sent.headers["Accept"] == "application/vnd.github+json"
    assert sent.headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert sent.headers["Authorization"] == f"Bearer {TOKEN}"


def test_a_token_without_expiry_returns_none(github):
    github.check(expires=None)
    assert gh.check_target(TOKEN, github.repo, github.workflow) is None


@pytest.mark.parametrize("value, expected", [
    ("2027-03-12 00:00:00 UTC", datetime(2027, 3, 12, tzinfo=timezone.utc)),
    ("2027-03-12 01:00:00 +0100", datetime(2027, 3, 12, tzinfo=timezone.utc)),
    ("soon", None), ("", None), (None, None)])
def test_expiry_header_parsing(value, expected):
    assert gh.parse_expiry(value) == expected


@pytest.mark.parametrize("status, message", [(401, gh.UNAUTHORIZED), (403, gh.FORBIDDEN), (404, gh.NOT_FOUND)])
def test_check_failures_have_specific_messages_without_the_token(github, status, message):
    github.check(status=status)
    with pytest.raises(gh.GitHubError) as err:
        gh.check_target(TOKEN, github.repo, github.workflow)
    assert (err.value.status, err.value.message) == (status, message)
    assert TOKEN not in str(err.value)


def test_a_workflow_missing_from_the_default_branch_is_the_404_message(github):
    github.check(workflow_status=404)
    with pytest.raises(gh.GitHubError) as err:
        gh.check_target(TOKEN, github.repo, github.workflow)
    assert "default branch" in err.value.message


def test_a_rate_limit_says_when_to_retry(github):
    reset = int(datetime.now(timezone.utc).timestamp()) + 42
    github.check(status=403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)})
    with pytest.raises(gh.RateLimited) as err:
        gh.check_target(TOKEN, github.repo, github.workflow)
    assert 40 <= err.value.retry_after <= 42
    assert err.value.message == f"GitHub rate limit, try again in {err.value.retry_after} s"


def test_redirects_are_not_followed(http):
    http.get(f"{gh.API}/repos/acme/obt").mock(
        return_value=httpx.Response(301, headers={"location": "https://evil.example/steal"}))
    with pytest.raises(gh.GitHubError):  # following it would hit an unrouted host and raise something else
        gh.check_target(TOKEN, "acme/obt", "qa-vision-run.yml")


def test_a_network_error_is_a_github_error_without_details(http):
    http.get(f"{gh.API}/repos/acme/obt").mock(side_effect=httpx.ConnectTimeout("boom"))
    with pytest.raises(gh.GitHubError) as err:
        gh.check_target(TOKEN, "acme/obt", "qa-vision-run.yml")
    assert err.value.status == 0 and TOKEN not in err.value.message


@pytest.mark.parametrize("repo, workflow", [
    ("acme", "x.yml"), ("acme/obt/x", "x.yml"), ("acme/..", "x.yml"), ("acme/.", "x.yml"),
    ("a" * 40 + "/x", "x.yml"), ("acme/obt", "x.json"), ("acme/obt", "../x.yml"), ("acme/obt", "a/x.yml")])
def test_names_are_checked_before_any_request(http, repo, workflow):
    with pytest.raises(ValueError):
        gh.check_target(TOKEN, repo, workflow)
    assert not http.calls


def test_dispatch_asks_for_run_details_and_returns_the_run(github):
    route = github.dispatch(run_id=501)
    result = gh.dispatch(TOKEN, github.repo, github.workflow, "main", {"paths": "[]", "names": "[]", "request_id": "7"})
    assert result == gh.DispatchResult(run_id=501, html_url=f"https://github.com/{github.repo}/actions/runs/501")
    assert route.calls.last.request.read() == (
        b'{"ref": "main", "inputs": {"paths": "[]", "names": "[]", "request_id": "7"}, "return_run_details": true}')


def test_a_204_dispatch_returns_none_for_the_matching_fallback(github):
    github.dispatch()
    assert gh.dispatch(TOKEN, github.repo, github.workflow, "main", {"request_id": "7"}) is None


@pytest.mark.parametrize("body", [{}, {"workflow_run_id": "501"}, {"workflow_run_id": True}, ["x"]])
def test_a_200_without_a_usable_run_id_also_falls_back(http, body):
    http.post(f"{gh.API}/repos/acme/obt/actions/workflows/qa-vision-run.yml/dispatches").mock(
        return_value=httpx.Response(200, json=body))
    assert gh.dispatch(TOKEN, "acme/obt", "qa-vision-run.yml", "main", {"request_id": "7"}) is None


def test_find_run_matches_the_exact_title(github):
    since = datetime(2026, 10, 7, 9, 59, tzinfo=timezone.utc)
    github.runs(github.run_body(2, 8), github.run_body(4, 7, title="QA Vision #77"), github.run_body(3, 7))
    assert gh.find_run(TOKEN, github.repo, github.workflow, "QA Vision #7", since)["id"] == 3


def test_find_run_sends_created_in_utc_z(github):
    route = github.runs()
    since = datetime(2026, 10, 7, 10, 59, tzinfo=timezone(timedelta(hours=1)))
    assert gh.find_run(TOKEN, github.repo, github.workflow, "QA Vision #7", since) is None
    params = route.calls.last.request.url.params
    assert params["created"] == ">=2026-10-07T09:59:00Z"
    assert params["event"] == "workflow_dispatch"


def test_find_run_skips_older_runs_other_events_and_claimed_ids(github):
    since = datetime(2026, 10, 7, 9, 59, tzinfo=timezone.utc)
    github.runs(
        github.run_body(1, 7, created_at="2026-10-07T09:40:00Z"),   # an older manual dispatch with the same title
        {**github.run_body(2, 7), "event": "push"},
        github.run_body(3, 7),                                       # already another request's run
        github.run_body(5, 7, created_at="2026-10-07T09:59:20Z"),
        github.run_body(4, 7, created_at="2026-10-07T09:59:10Z"),   # ours: GitHub's clock is 50 s behind ours
    )
    run = gh.find_run(TOKEN, github.repo, github.workflow, "QA Vision #7", since, exclude_ids=frozenset({3}))
    assert run["id"] == 4   # the oldest remaining match


def test_get_and_cancel_a_run(github):
    github.run(github.run_body(9, 7, status="in_progress"))
    cancel = github.cancel(9)
    assert gh.get_run(TOKEN, github.repo, 9)["status"] == "in_progress"
    gh.cancel_run(TOKEN, github.repo, 9)
    assert cancel.call_count == 1


def test_cancelling_a_finished_run_is_a_409_github_error(github):
    github.cancel(9, status=409)
    with pytest.raises(gh.GitHubError) as err:
        gh.cancel_run(TOKEN, github.repo, 9)
    assert err.value.status == 409
