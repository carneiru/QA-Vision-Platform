import httpx
import pytest

from src.project.utils.repo_verifier import verify

GITHUB = "https://api.github.com/repos/acme/shop"
GITLAB = "https://gitlab.com/api/v4/projects/group%2Fsub%2Fproject"


def test_github_200_is_verified_with_default_branch(http):
    http.get(GITHUB).mock(return_value=httpx.Response(200, json={"default_branch": "develop"}))
    result = verify("github", "acme", "shop", timeout=3.0)
    assert (result.status, result.default_branch) == ("verified", "develop")


def test_gitlab_uses_the_url_encoded_full_path(http):
    route = http.get(GITLAB).mock(return_value=httpx.Response(200, json={"default_branch": "main"}))
    result = verify("gitlab", "group/sub", "project", timeout=3.0)
    assert route.called
    assert (result.status, result.default_branch) == ("verified", "main")


def test_verified_without_a_default_branch(http):
    # an empty GitLab project reports default_branch: null
    http.get(GITHUB).mock(return_value=httpx.Response(200, json={"default_branch": None}))
    assert verify("github", "acme", "shop", timeout=3.0).default_branch is None


def test_404_is_not_found(http):
    http.get(GITHUB).mock(return_value=httpx.Response(404, json={"message": "Not Found"}))
    assert verify("github", "acme", "shop", timeout=3.0).status == "not_found"


@pytest.mark.parametrize("status_code", [403, 429, 500, 502, 503])
def test_rate_limit_and_server_errors_are_unchecked(http, status_code):
    http.get(GITHUB).mock(return_value=httpx.Response(status_code))
    assert verify("github", "acme", "shop", timeout=3.0).status == "unchecked"


def test_redirect_is_not_followed(http):
    # GitHub answers 301 for a renamed repository; following redirects would let a response
    # send this server anywhere, so it is reported as unchecked instead
    http.get(GITHUB).mock(return_value=httpx.Response(301, headers={"Location": "https://example.com/"}))
    assert verify("github", "acme", "shop", timeout=3.0).status == "unchecked"


def test_timeout_is_unchecked(http):
    http.get(GITHUB).mock(side_effect=httpx.ConnectTimeout("slow"))
    assert verify("github", "acme", "shop", timeout=3.0).status == "unchecked"


def test_non_json_200_is_unchecked(http):
    http.get(GITHUB).mock(return_value=httpx.Response(200, text="<html>"))
    assert verify("github", "acme", "shop", timeout=3.0).status == "unchecked"


def test_no_credentials_are_sent(http):
    route = http.get(GITHUB).mock(return_value=httpx.Response(200, json={"default_branch": "main"}))
    verify("github", "acme", "shop", timeout=3.0)
    assert "authorization" not in {key.lower() for key in route.calls.last.request.headers.keys()}


def test_unknown_provider_is_a_programming_error():
    with pytest.raises(ValueError):
        verify("bitbucket", "acme", "shop", timeout=3.0)
