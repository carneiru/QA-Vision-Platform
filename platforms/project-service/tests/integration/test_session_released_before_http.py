"""A slow upstream must never pin a database connection: every outbound HTTP
call (organization-service members/me, the repository provider) happens with
no transaction open on the request's session, so the connection is back in
the pool while we wait."""
import httpx

from src.project.core.config import settings
from src.project.models.repository import Repository

ORG_ME = "{base}/api/v1/organizations/1/members/me"
GITHUB_API = "https://api.github.com/repos/acme/shop"


def _spy(db, seen, response):
    def handler(request):
        seen.append(db.in_transaction())
        return response
    return handler


def test_members_me_is_called_with_no_open_transaction(client, auth, db, http, make_project):
    project = make_project()
    seen = []
    http.get(ORG_ME.format(base=settings.ORGANIZATION_SERVICE_URL)).mock(
        side_effect=_spy(db, seen, httpx.Response(200, json={"role": "owner"})))

    response = client.get(f"/api/v1/projects/{project.id}", headers=auth())
    assert response.status_code == 200, response.text
    assert seen == [False]


def test_adding_a_repository_verifies_with_no_open_transaction(client, auth, db, http, org_role, make_project):
    project = make_project()
    org_role("owner")
    seen = []
    http.get(GITHUB_API).mock(side_effect=_spy(
        db, seen, httpx.Response(200, json={"default_branch": "main", "private": False})))

    response = client.post(f"/api/v1/projects/{project.id}/repositories",
                           json={"url": "https://github.com/acme/shop"}, headers=auth())
    assert response.status_code == 201, response.text
    assert seen == [False]


def test_reverifying_a_repository_runs_with_no_open_transaction(client, auth, db, http, org_role, make_project):
    project = make_project()
    org_role("owner")
    repo = Repository(project_id=project.id, provider="github", owner="acme", name="shop",
                      full_name_key="acme/shop", url="https://github.com/acme/shop",
                      default_branch="main", default_branch_is_user_set=False)
    db.add(repo)
    db.commit()
    seen = []
    http.get(GITHUB_API).mock(side_effect=_spy(
        db, seen, httpx.Response(200, json={"default_branch": "trunk", "private": False})))

    response = client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth())
    assert response.status_code == 200, response.text
    assert seen == [False]
    assert response.json()["default_branch"] == "trunk"  # the result is still applied and saved
