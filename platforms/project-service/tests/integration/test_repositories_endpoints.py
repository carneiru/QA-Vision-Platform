from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.project.core.config import settings
from src.project.models.repository import Repository

ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")
EDITORS = ("owner", "admin", "member")
GITHUB_API = "https://api.github.com/repos/acme/shop"


@pytest.fixture
def github(http):
    """Mock the GitHub API for acme/shop; github(status, branch) replaces the previous answer."""

    def _set(status_code=200, branch="main"):
        body = {"default_branch": branch} if status_code == 200 else {"message": "x"}
        return http.get(GITHUB_API, name="github-acme-shop").mock(return_value=httpx.Response(status_code, json=body))

    return _set


@pytest.fixture
def add_repo(db):
    def _add(project, **overrides):
        values = dict(
            project_id=project.id, provider="github", owner="acme", name="shop", full_name_key="acme/shop",
            url="https://github.com/acme/shop", default_branch="main", default_branch_is_user_set=False,
            verification_status="unchecked", verified_at=None,
        )
        values.update(overrides)
        repo = Repository(**values)
        db.add(repo)
        db.commit()
        db.refresh(repo)
        return repo

    return _add


@pytest.mark.parametrize("role", ALL_ROLES)
def test_list_is_open_to_every_role(client, auth, org_role, make_project, role):
    project = make_project()
    org_role(role)
    assert client.get(f"/api/v1/projects/{project.id}/repositories", headers=auth()).status_code == 200


@pytest.mark.parametrize("role", ALL_ROLES)
def test_add_is_for_editors(client, auth, org_role, make_project, github, role):
    project = make_project()
    org_role(role)
    github()
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories", json={"url": "https://github.com/acme/shop"}, headers=auth()
    )
    assert response.status_code == (201 if role in EDITORS else 403)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_verify_is_for_editors(client, auth, org_role, make_project, add_repo, github, role):
    project = make_project()
    repo = add_repo(project)
    org_role(role)
    github()
    response = client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth())
    assert response.status_code == (200 if role in EDITORS else 403)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_delete_is_for_editors(client, auth, org_role, make_project, add_repo, role):
    project = make_project()
    repo = add_repo(project)
    org_role(role)
    response = client.delete(f"/api/v1/projects/{project.id}/repositories/{repo.id}", headers=auth())
    assert response.status_code == (204 if role in EDITORS else 403)


def test_add_verified_repository(client, auth, org_role, make_project, github):
    project = make_project()
    org_role("member")
    github(branch="develop")
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories",
        json={"url": "git@github.com:acme/shop.git"},
        headers=auth(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["provider"] == "github"
    assert (body["owner"], body["name"]) == ("acme", "shop")
    assert body["url"] == "https://github.com/acme/shop"
    assert body["verification_status"] == "verified"
    assert body["verified_at"] is not None
    assert body["default_branch"] == "develop"
    assert body["default_branch_is_user_set"] is False


def test_user_branch_wins_over_provider(client, auth, org_role, make_project, github):
    project = make_project()
    org_role("member")
    github(branch="develop")
    body = client.post(
        f"/api/v1/projects/{project.id}/repositories",
        json={"url": "https://github.com/acme/shop", "default_branch": "release"},
        headers=auth(),
    ).json()
    assert body["default_branch"] == "release"
    assert body["default_branch_is_user_set"] is True


@pytest.mark.parametrize("status_code, expected", [(404, "not_found"), (403, "unchecked"), (500, "unchecked")])
def test_failed_check_still_saves_with_main_fallback(client, auth, org_role, make_project, github, status_code, expected):
    project = make_project()
    org_role("member")
    github(status_code=status_code)
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories", json={"url": "https://github.com/acme/shop"}, headers=auth()
    )
    assert response.status_code == 201
    assert response.json()["verification_status"] == expected
    assert response.json()["default_branch"] == "main"


def test_provider_timeout_still_saves_unchecked(client, auth, org_role, make_project, http):
    project = make_project()
    org_role("member")
    http.get(GITHUB_API).mock(side_effect=httpx.ReadTimeout("slow"))
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories", json={"url": "https://github.com/acme/shop"}, headers=auth()
    )
    assert response.status_code == 201
    assert response.json()["verification_status"] == "unchecked"


@pytest.mark.parametrize(
    "url", ["https://bitbucket.org/acme/shop", "https://github.com.evil.com/acme/shop", "not a url"]
)
def test_unsupported_url_is_422_and_no_provider_call(client, auth, org_role, make_project, http, url):
    project = make_project()
    route = org_role("member")
    response = client.post(f"/api/v1/projects/{project.id}/repositories", json={"url": url}, headers=auth())
    assert response.status_code == 422
    # only the members/me call happened
    assert [call.request.url.host for call in http.calls] == [route.calls.last.request.url.host]


def test_duplicate_in_same_project_is_409_regardless_of_case(client, auth, org_role, make_project, add_repo, http):
    project = make_project()
    add_repo(project)
    org_role("member")
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories", json={"url": "https://github.com/ACME/Shop"}, headers=auth()
    )
    assert response.status_code == 409
    # the duplicate is caught before spending provider quota
    assert all(call.request.url.host != "api.github.com" for call in http.calls)


def test_same_repository_in_two_projects_is_allowed(client, auth, org_role, make_project, add_repo, github):
    first = make_project(name="A", slug="a")
    add_repo(first)
    second = make_project(name="B", slug="b")
    org_role("member")
    github()
    response = client.post(
        f"/api/v1/projects/{second.id}/repositories", json={"url": "https://github.com/acme/shop"}, headers=auth()
    )
    assert response.status_code == 201


def test_verify_within_cooldown_does_not_call_the_provider(client, auth, org_role, make_project, add_repo, github):
    project = make_project()
    repo = add_repo(project, verification_status="not_found", verified_at=datetime.now(timezone.utc))
    org_role("member")
    route = github()
    response = client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth())
    assert response.status_code == 200
    assert response.json()["verification_status"] == "not_found"
    assert not route.called


def test_verify_after_cooldown_updates_status_and_provider_branch(client, auth, org_role, make_project, add_repo, github):
    project = make_project()
    stale = datetime.now(timezone.utc) - timedelta(seconds=settings.REPO_VERIFY_COOLDOWN_SECONDS + 5)
    repo = add_repo(project, verification_status="unchecked", verified_at=stale)
    org_role("member")
    route = github(branch="develop")
    body = client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth()).json()
    assert route.called
    assert body["verification_status"] == "verified"
    assert body["default_branch"] == "develop"


def test_verify_never_overwrites_a_user_branch(client, auth, org_role, make_project, add_repo, github):
    project = make_project()
    repo = add_repo(project, default_branch="release", default_branch_is_user_set=True)
    org_role("member")
    github(branch="develop")
    body = client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth()).json()
    assert body["default_branch"] == "release"


def test_failed_check_also_starts_the_cooldown(client, auth, org_role, make_project, add_repo, github):
    project = make_project()
    repo = add_repo(project)
    org_role("member")
    first = github(status_code=500)
    client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth())
    assert first.call_count == 1
    client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth())
    assert first.call_count == 1


def test_repository_of_another_project_is_404(client, auth, org_role, make_project, add_repo):
    mine = make_project(name="A", slug="a")
    other = make_project(name="B", slug="b")
    repo = add_repo(other)
    org_role("member")
    assert client.delete(f"/api/v1/projects/{mine.id}/repositories/{repo.id}", headers=auth()).status_code == 404
    assert client.post(f"/api/v1/projects/{mine.id}/repositories/{repo.id}/verify", headers=auth()).status_code == 404


def test_repositories_of_a_deleted_project_are_unreachable(client, auth, org_role, make_project, add_repo):
    project = make_project()
    add_repo(project)
    org_role("owner")
    client.delete(f"/api/v1/projects/{project.id}", headers=auth())
    assert client.get(f"/api/v1/projects/{project.id}/repositories", headers=auth()).status_code == 404


def test_delete_removes_the_repository(client, auth, org_role, make_project, add_repo):
    project = make_project()
    repo = add_repo(project)
    org_role("member")
    client.delete(f"/api/v1/projects/{project.id}/repositories/{repo.id}", headers=auth())
    assert client.get(f"/api/v1/projects/{project.id}/repositories", headers=auth()).json() == []


def test_blank_branch_is_422(client, auth, org_role, make_project):
    project = make_project()
    org_role("member")
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories",
        json={"url": "https://github.com/acme/shop", "default_branch": "  "},
        headers=auth(),
    )
    assert response.status_code == 422


def test_add_an_azure_devops_repository(client, auth, org_role, make_project, http):
    project = make_project()
    org_role("member")
    http.get("https://dev.azure.com/acme/Shop%20QA/_apis/git/repositories/e2e").mock(
        return_value=httpx.Response(200, json={"defaultBranch": "refs/heads/develop"})
    )
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories",
        json={"url": "https://acme@dev.azure.com/acme/Shop%20QA/_git/e2e"},
        headers=auth(),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["provider"], body["owner"], body["name"]) == ("azure_devops", "acme/Shop QA", "e2e")
    assert body["url"] == "https://dev.azure.com/acme/Shop%20QA/_git/e2e"
    assert (body["verification_status"], body["default_branch"]) == ("verified", "develop")
