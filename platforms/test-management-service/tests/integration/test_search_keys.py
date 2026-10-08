"""Case key search (TC-12, tc12, 12) and suite name search."""
import pytest

P = "/api/v1/projects/1"


def make_cases(client, auth, count, project=1, titles=None):
    for i in range(1, count + 1):
        title = (titles or {}).get(i, f"case {i}")
        assert client.post(f"/api/v1/projects/{project}/cases", json={"title": title}, headers=auth()).status_code == 201


def numbers(response):
    assert response.status_code == 200, response.text
    return [c["number"] for c in response.json()["items"]]


@pytest.fixture
def twelve(client, auth, project_role):
    project_role("member", project_id=1)
    project_role("member", project_id=2)
    make_cases(client, auth, 13, titles={3: "mentions TC-12 in text", 5: "12 angry men"})
    return client


@pytest.mark.parametrize("term", ["TC-12", "tc12", "12", "  Tc-12 ", "TC12"])
def test_get_key_search_puts_the_case_first(twelve, auth, term):
    found = numbers(twelve.get(f"{P}/cases", params={"search": term}, headers=auth()))
    assert found[0] == 12


def test_key_match_is_ored_with_title_match(twelve, auth):
    assert numbers(twelve.get(f"{P}/cases", params={"search": "12"}, headers=auth())) == [12, 3, 5]
    assert numbers(twelve.get(f"{P}/cases", params={"search": "TC-12"}, headers=auth())) == [12, 3]


def test_post_search_finds_the_key_first(twelve, auth):
    for term in ("TC-12", "tc12", "12"):
        found = numbers(twelve.post(f"{P}/cases/search", json={"search": term}, headers=auth()))
        assert found[0] == 12


def test_non_numeric_search_is_unchanged(twelve, auth):
    assert numbers(twelve.get(f"{P}/cases", params={"search": "angry"}, headers=auth())) == [5]
    assert numbers(twelve.get(f"{P}/cases", params={"search": "TC-1x"}, headers=auth())) == []
    assert numbers(twelve.get(f"{P}/cases", params={"search": "TC-12 text"}, headers=auth())) == []


def test_key_search_total_and_paging(twelve, auth):
    body = twelve.get(f"{P}/cases", params={"search": "12", "limit": 1}, headers=auth()).json()
    assert body["total"] == 3 and [c["number"] for c in body["items"]] == [12]
    body = twelve.get(f"{P}/cases", params={"search": "12", "limit": 1, "offset": 1}, headers=auth()).json()
    assert [c["number"] for c in body["items"]] == [3]


def test_key_search_is_project_isolated(twelve, auth):
    make_cases(twelve, auth, 2, project=2)
    assert numbers(twelve.get("/api/v1/projects/2/cases", params={"search": "TC-12"}, headers=auth())) == []
    assert numbers(twelve.post("/api/v1/projects/2/cases/search", json={"search": "12"}, headers=auth())) == []


def test_key_search_still_respects_other_filters(twelve, auth):
    assert numbers(twelve.get(f"{P}/cases", params={"search": "12", "status": "archived"}, headers=auth())) == []


@pytest.fixture
def suites(client, auth, project_role):
    project_role("member", project_id=1)
    project_role("member", project_id=2)
    for name in ("Smoke", "Regression 100%", "Regression_x", "Regression-y", "smoke (web)"):
        assert client.post(f"{P}/suites", json={"name": name}, headers=auth()).status_code == 201
    assert client.post("/api/v1/projects/2/suites", json={"name": "Smoke other"}, headers=auth()).status_code == 201
    return client


def names(response):
    assert response.status_code == 200, response.text
    return [s["name"] for s in response.json()]


def test_suite_search_is_a_case_insensitive_contains(suites, auth):
    assert names(suites.get(f"{P}/suites", params={"search": "smo"}, headers=auth())) == ["Smoke", "smoke (web)"]
    assert names(suites.get(f"{P}/suites", params={"search": "GRESS"}, headers=auth())) == [
        "Regression 100%", "Regression-y", "Regression_x"]


def test_suite_search_escapes_like_wildcards(suites, auth):
    assert names(suites.get(f"{P}/suites", params={"search": "%"}, headers=auth())) == ["Regression 100%"]
    assert names(suites.get(f"{P}/suites", params={"search": "n_x"}, headers=auth())) == ["Regression_x"]


def test_suite_search_is_project_isolated(suites, auth):
    assert names(suites.get("/api/v1/projects/2/suites", params={"search": "smoke"}, headers=auth())) == ["Smoke other"]


def test_suite_without_search_lists_all(suites, auth):
    assert len(names(suites.get(f"{P}/suites", headers=auth()))) == 5


@pytest.mark.parametrize("term", ["", "x" * 201, "a\x00b"])
def test_suite_search_validates_length_and_nul(suites, auth, term):
    assert suites.get(f"{P}/suites", params={"search": term}, headers=auth()).status_code == 422


def test_suite_search_is_readable_by_viewers(client, auth, project_role):
    project_role("viewer")
    assert client.get(f"{P}/suites", params={"search": "x"}, headers=auth()).status_code == 200
