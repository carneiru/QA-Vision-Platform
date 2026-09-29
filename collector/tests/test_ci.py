from qav_collector.ci import CIInfo, detect, sanitize_key

GITHUB = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_SHA": "a" * 40,
    "GITHUB_REF_NAME": "main",
    "GITHUB_SERVER_URL": "https://github.com",
    "GITHUB_REPOSITORY": "acme/shop",
    "GITHUB_RUN_ID": "123",
    "GITHUB_RUN_ATTEMPT": "2",
    "GITHUB_JOB": "test",
}


def test_github_actions():
    assert detect(GITHUB) == CIInfo(
        provider="github_actions",
        commit="a" * 40,
        branch="main",
        run_url="https://github.com/acme/shop/actions/runs/123",
        idempotency_key="gh-123-2-test",
    )


def test_github_pull_request_uses_the_head_branch():
    info = detect({**GITHUB, "GITHUB_REF_NAME": "42/merge", "GITHUB_HEAD_REF": "feature/cart"})
    assert info.branch == "feature/cart"


def test_github_without_a_run_id_has_no_key_and_no_run_url():
    env = dict(GITHUB)
    del env["GITHUB_RUN_ID"]
    info = detect(env)
    assert info.provider == "github_actions"
    assert info.idempotency_key is None and info.run_url is None


def test_github_attempt_defaults_to_1():
    env = dict(GITHUB)
    del env["GITHUB_RUN_ATTEMPT"]
    assert detect(env).idempotency_key == "gh-123-1-test"


def test_gitlab_ci():
    env = {
        "GITLAB_CI": "true",
        "CI_COMMIT_SHA": "b" * 40,
        "CI_COMMIT_REF_NAME": "develop",
        "CI_JOB_URL": "https://gitlab.com/acme/shop/-/jobs/77",
        "CI_JOB_ID": "77",
    }
    assert detect(env) == CIInfo(
        provider="gitlab_ci",
        commit="b" * 40,
        branch="develop",
        run_url="https://gitlab.com/acme/shop/-/jobs/77",
        idempotency_key="gl-77",
    )


def test_jenkins_strips_origin_and_sanitises_the_build_tag():
    env = {
        "JENKINS_URL": "https://ci.acme.test/",
        "GIT_COMMIT": "c" * 40,
        "GIT_BRANCH": "origin/release/1.2",
        "BUILD_URL": "https://ci.acme.test/job/shop/12/",
        "BUILD_TAG": "jenkins-shop tests-12",
    }
    assert detect(env) == CIInfo(
        provider="jenkins",
        commit="c" * 40,
        branch="release/1.2",
        run_url="https://ci.acme.test/job/shop/12/",
        idempotency_key="jk-jenkins-shop-tests-12",
    )


def test_no_ci_is_local():
    assert detect({}) == CIInfo(provider="local")
    assert detect({"GITHUB_ACTIONS": "false", "GITLAB_CI": ""}) == CIInfo(provider="local")


def test_blank_variables_count_as_missing():
    assert detect({**GITHUB, "GITHUB_SHA": "  ", "GITHUB_HEAD_REF": ""}).commit is None
    assert detect({**GITHUB, "GITHUB_HEAD_REF": ""}).branch == "main"


def test_sanitize_key():
    assert sanitize_key("a bé\n") == "a-b--"
    assert sanitize_key("x" * 300) == "x" * 200
    assert sanitize_key("") is None
