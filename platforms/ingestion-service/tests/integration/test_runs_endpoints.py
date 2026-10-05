from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.ingestion.models import Run, RunResult

ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")


@pytest.fixture
def make_run(db, make_key):
    key_row, _ = make_key()

    def _make(project_id=1, branch="main", statuses=("passed", "failed"), minutes_ago=0, **fields):
        now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        run = Run(project_id=project_id, api_key_id=key_row.id, request_hash="h",
                  branch=branch, started_at=now - timedelta(seconds=1), finished_at=now, duration_ms=1000,
                  total=len(statuses), passed=statuses.count("passed"), failed=statuses.count("failed"),
                  skipped=statuses.count("skipped"), errored=statuses.count("errored"), created_at=now, **{"ci_provider": "local", **fields})
        db.add(run)
        db.flush()
        for i, st in enumerate(statuses):
            db.add(RunResult(run_id=run.id, test_key=f"{i:064d}", name=f"t{i}", status=st, duration_ms=1))
        db.commit()
        db.refresh(run)
        return run

    return _make


@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_role_can_list_runs(client, auth, project_role, role):
    project_role(role)
    assert client.get("/api/v1/projects/1/runs", headers=auth()).status_code == 200


@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_role_can_get_a_run(client, auth, project_role, make_run, role):
    run = make_run()
    project_role(role)
    assert client.get(f"/api/v1/runs/{run.id}", headers=auth()).status_code == 200


def test_list_is_newest_first_this_project_only_with_counts(client, auth, project_role, make_run):
    older = make_run(minutes_ago=10)
    newer = make_run(minutes_ago=1)
    make_run(project_id=2)
    project_role("viewer")
    body = client.get("/api/v1/projects/1/runs", headers=auth()).json()
    assert [r["id"] for r in body] == [newer.id, older.id]
    assert (body[0]["total"], body[0]["passed"], body[0]["failed"]) == (2, 1, 1)
    assert "results" not in body[0]


def test_list_filters_by_branch(client, auth, project_role, make_run):
    make_run(branch="main")
    feature = make_run(branch="feature/x")
    project_role("viewer")
    body = client.get("/api/v1/projects/1/runs?branch=feature/x", headers=auth()).json()
    assert [r["id"] for r in body] == [feature.id]


def test_list_pagination(client, auth, project_role, make_run):
    runs = [make_run(minutes_ago=m) for m in (5, 4, 3, 2, 1)]
    project_role("viewer")
    page = client.get("/api/v1/projects/1/runs?limit=2&offset=1", headers=auth()).json()
    assert [r["id"] for r in page] == [runs[3].id, runs[2].id]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_list_rejects_bad_pagination(client, auth, project_role, query):
    project_role("viewer")
    assert client.get(f"/api/v1/projects/1/runs?{query}", headers=auth()).status_code == 422


def test_get_run_returns_results_in_order(client, auth, project_role, make_run):
    run = make_run(statuses=("passed", "failed", "skipped"))
    project_role("viewer")
    body = client.get(f"/api/v1/runs/{run.id}", headers=auth()).json()
    assert [r["name"] for r in body["results"]] == ["t0", "t1", "t2"]
    assert body["results"][1]["status"] == "failed"
    assert set(body["results"][0]) >= {"test_key", "suite", "class_name", "name", "status", "duration_ms",
                                       "message", "details", "truncated", "file"}


def test_get_run_filters_by_status(client, auth, project_role, make_run):
    run = make_run(statuses=("passed", "failed", "failed"))
    project_role("viewer")
    body = client.get(f"/api/v1/runs/{run.id}?status=failed", headers=auth()).json()
    assert [r["status"] for r in body["results"]] == ["failed", "failed"]
    assert body["total"] == 3  # the run's counts are unaffected by the filter


def test_get_run_invalid_status_filter_is_422(client, auth, project_role, make_run):
    run = make_run()
    project_role("viewer")
    assert client.get(f"/api/v1/runs/{run.id}?status=flaky", headers=auth()).status_code == 422


def test_missing_run_is_404_without_calling_project_service(client, auth, http):
    assert client.get("/api/v1/runs/999", headers=auth()).status_code == 404
    assert not http.calls


def test_run_of_a_project_the_caller_cannot_see_is_404(client, auth, project_role, make_run):
    run = make_run(project_id=3)
    project_role(project_id=3, status_code=404, body={"detail": "Project not found"})
    response = client.get(f"/api/v1/runs/{run.id}", headers=auth())
    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


def test_project_service_down_is_503(client, auth, project_role, make_run):
    run = make_run()
    project_role(exc=httpx.ConnectError("refused"))
    assert client.get(f"/api/v1/runs/{run.id}", headers=auth()).status_code == 503
    assert client.get("/api/v1/projects/1/runs", headers=auth()).status_code == 503


def test_non_member_listing_is_404(client, auth, project_role):
    project_role(status_code=404, body={"detail": "Project not found"})
    assert client.get("/api/v1/projects/1/runs", headers=auth()).status_code == 404


def test_missing_token_is_401(client):
    assert client.get("/api/v1/projects/1/runs").status_code == 401
    assert client.get("/api/v1/runs/1").status_code == 401



def ids(client, auth, query):
    response = client.get(f"/api/v1/projects/1/runs?{query}", headers=auth())
    assert response.status_code == 200, response.text
    return {r["id"] for r in response.json()}


def test_list_filters_failing_and_passing(client, auth, project_role, make_run):
    red = make_run(statuses=("passed", "failed"))
    broken = make_run(statuses=("errored",))
    green = make_run(statuses=("passed", "skipped"))
    project_role("viewer")
    assert ids(client, auth, "status=failing") == {red.id, broken.id}
    assert ids(client, auth, "status=passing") == {green.id}


def test_list_filters_by_environment_and_ci(client, auth, project_role, make_run):
    staging = make_run(environment="staging", ci_provider="azure_pipelines")
    make_run(environment="prod", ci_provider="azure_pipelines")
    make_run(environment="staging", ci_provider="github_actions")
    project_role("viewer")
    assert ids(client, auth, "environment=staging&ci_provider=azure_pipelines") == {staging.id}


def test_list_filters_by_commit_prefix_any_case(client, auth, project_role, make_run):
    hit = make_run(commit_sha="abc1234def")
    make_run(commit_sha="ffff000")
    project_role("viewer")
    assert ids(client, auth, "commit=ABC12") == {hit.id}


@pytest.mark.parametrize("commit", ["abc", "xyz12", "a%25bc1"])
def test_list_rejects_bad_commit_prefix(client, auth, project_role, commit):
    project_role("viewer")
    assert client.get(f"/api/v1/projects/1/runs?commit={commit}", headers=auth()).status_code == 422


def test_list_filters_by_pull_request(client, auth, project_role, make_run):
    pr = make_run(pr_number=42)
    make_run(pr_number=7)
    project_role("viewer")
    assert ids(client, auth, "pr=42") == {pr.id}


def test_list_filters_by_author_substring_with_literal_wildcards(client, auth, project_role, make_run):
    ana = make_run(commit_author="Ana Silva")
    make_run(commit_author="Bruno")
    odd = make_run(commit_author="100%_bot")
    project_role("viewer")
    assert ids(client, auth, "author=silva") == {ana.id}
    # % and _ match themselves, not "anything"
    assert ids(client, auth, "author=%25_") == {odd.id}


def test_list_filters_by_started_date_range(client, auth, project_role, make_run):
    old = make_run(minutes_ago=3 * 24 * 60)
    recent = make_run(minutes_ago=5)
    project_role("viewer")
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert ids(client, auth, f"since={since.replace('+', '%2B')}") == {recent.id}
    until = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    assert ids(client, auth, f"until={until.replace('+', '%2B')}") == {old.id}


def test_list_filters_combine(client, auth, project_role, make_run):
    hit = make_run(branch="main", statuses=("failed",), environment="qa")
    make_run(branch="main", statuses=("passed",), environment="qa")
    make_run(branch="dev", statuses=("failed",), environment="qa")
    project_role("viewer")
    assert ids(client, auth, "branch=main&status=failing&environment=qa") == {hit.id}


@pytest.mark.parametrize("query", ["status=red", "ci_provider=travis", "pr=0", "since=yesterday"])
def test_list_rejects_bad_filters(client, auth, project_role, query):
    project_role("viewer")
    assert client.get(f"/api/v1/projects/1/runs?{query}", headers=auth()).status_code == 422
