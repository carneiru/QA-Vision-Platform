import pytest

from src.project.utils.repo_url import parse_repo_url


@pytest.mark.parametrize(
    "raw",
    [
        "https://github.com/acme/shop",
        "https://github.com/acme/shop/",
        "https://github.com/acme/shop.git",
        "http://github.com/acme/shop",
        "https://www.github.com/acme/shop",
        "https://GitHub.com/acme/shop",
        "https://github.com/acme/shop/tree/main",
        "https://github.com/acme/shop/blob/main/README.md",
        "https://github.com/acme/shop?tab=readme-ov-file",
        "https://github.com/acme/shop#readme",
        "git@github.com:acme/shop.git",
        "git@github.com:acme/shop",
        "  https://github.com/acme/shop  ",
    ],
)
def test_github_forms_parse_to_the_same_repository(raw):
    parsed = parse_repo_url(raw)
    assert parsed.provider == "github"
    assert (parsed.owner, parsed.name) == ("acme", "shop")
    assert parsed.full_name_key == "acme/shop"
    assert parsed.url == "https://github.com/acme/shop"


def test_case_is_kept_for_display_but_not_for_the_key():
    parsed = parse_repo_url("https://github.com/Acme/Shop")
    assert (parsed.owner, parsed.name) == ("Acme", "Shop")
    assert parsed.full_name_key == "acme/shop"
    assert parsed.url == "https://github.com/Acme/Shop"


@pytest.mark.parametrize(
    "raw, owner, name",
    [
        ("https://gitlab.com/group/project", "group", "project"),
        ("https://gitlab.com/group/sub/project", "group/sub", "project"),
        ("https://gitlab.com/group/sub/project/-/tree/main", "group/sub", "project"),
        ("https://gitlab.com/group/sub/project.git", "group/sub", "project"),
        ("git@gitlab.com:group/sub/project.git", "group/sub", "project"),
    ],
)
def test_gitlab_forms(raw, owner, name):
    parsed = parse_repo_url(raw)
    assert parsed.provider == "gitlab"
    assert (parsed.owner, parsed.name) == (owner, name)
    assert parsed.url == f"https://gitlab.com/{owner}/{name}"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "github.com/acme/shop",                     # no scheme
        "ftp://github.com/acme/shop",
        "https://bitbucket.org/acme/shop",
        "https://gitlab.example.com/acme/shop",     # self-hosted GitLab is out of scope
        "https://github.com.evil.com/acme/shop",
        "https://evil.com/github.com/acme/shop",
        "https://127.0.0.1/acme/shop",
        "https://github.com:8443/acme/shop",
        "https://user@github.com/acme/shop",
        "https://user:pw@github.com/acme/shop",
        "https://github.com/acme",                  # no repository name
        "https://github.com/",
        "https://github.com/../shop",
        "https://github.com/acme/..",
        "https://github.com/acme/....git",
        "https://github.com/.../shop",
        "https://gitlab.com/acme/..../project",
        "https://github.com/acme/sh%2Fop",
        "https://github.com/ac me/shop",
        "https://github.com//shop",
        "https://gitlab.com/project",               # GitLab needs a namespace
        "https://gitlab.com/" + "/".join(["g"] * 21) + "/p",   # more than 20 segments
        "git@evil.com:acme/shop.git",
    ],
)
def test_rejected_inputs(raw):
    with pytest.raises(ValueError):
        parse_repo_url(raw)


def test_rejection_message_names_the_supported_hosts():
    with pytest.raises(ValueError, match="github.com and gitlab.com"):
        parse_repo_url("https://bitbucket.org/acme/shop")


@pytest.mark.parametrize("raw, name", [("https://github.com/acme/.github", ".github"), ("https://github.com/acme/shop.io", "shop.io")])
def test_names_with_dots_are_still_accepted(raw, name):
    assert parse_repo_url(raw).name == name


def test_a_deep_gitlab_path_with_long_segments_is_rejected():
    segments = ["g" * 20 for _ in range(20)]
    raw = "https://gitlab.com/" + "/".join(segments)
    with pytest.raises(ValueError, match="too long"):
        parse_repo_url(raw)


def test_a_256_character_github_name_is_rejected():
    raw = f"https://github.com/acme/{'a' * 256}"
    with pytest.raises(ValueError, match="too long"):
        parse_repo_url(raw)


def test_a_255_character_github_name_is_accepted():
    name = "a" * 255
    parsed = parse_repo_url(f"https://github.com/acme/{name}")
    assert parsed.name == name
