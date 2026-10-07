"""Case list filters: folder, link, feature, Azure DevOps item, test keys; folder and feature facets."""
import pytest

from qeos_shared.keys import test_key as make_test_key

P = "/api/v1/projects/1"


def feature(name, *scenarios):
    return f"Feature: {name}\n" + "".join(f"  {tags}\n  Scenario: {s}\n    Given {s}\n" for s, tags in scenarios)


FILES = [
    ("tests/features/hotel/a.feature", feature("Hotel", ("h1", "@ado:123"))),
    ("tests/features/hotels/booking/b.feature", feature("Hotels booking", ("b1", ""), ("b2", "@ado:456"))),
    ("tests/features/flights_amadeus/c.feature", feature("Amadeus", ("f1", ""))),
    ("tests/features/flightsXamadeus/d.feature", feature("Lookalike", ("x1", ""))),
]


@pytest.fixture
def seeded(client, auth, project_role):
    project_role("member")
    body = {"files": [{"path": p, "content": c} for p, c in FILES]}
    assert client.post(f"{P}/cases/import", json=body, headers=auth()).status_code == 200
    client.post(f"{P}/cases", json={"title": "manual"}, headers=auth())
    return client


def titles(response):
    assert response.status_code == 200, response.text
    return sorted(c["title"] for c in response.json()["items"])


def test_folder_includes_subfolders(seeded, auth):
    assert titles(seeded.get(f"{P}/cases?folder=tests/features/hotels", headers=auth())) == ["b1", "b2"]
    assert titles(seeded.get(f"{P}/cases?folder=tests/features", headers=auth())) == ["b1", "b2", "f1", "h1", "x1"]


def test_folder_matches_whole_segments(seeded, auth):
    assert titles(seeded.get(f"{P}/cases?folder=tests/features/hotel", headers=auth())) == ["h1"]


def test_folder_names_are_matched_literally(seeded, auth):
    assert titles(seeded.get(f"{P}/cases?folder=tests/features/flights_amadeus", headers=auth())) == ["f1"]


def test_linked_feature_and_ado(seeded, auth):
    assert titles(seeded.get(f"{P}/cases?linked=false", headers=auth())) == ["manual"]
    assert "manual" not in titles(seeded.get(f"{P}/cases?linked=true", headers=auth()))
    assert titles(seeded.get(f"{P}/cases?feature=Hotels%20booking", headers=auth())) == ["b1", "b2"]
    assert titles(seeded.get(f"{P}/cases?ado=456", headers=auth())) == ["b2"]
    assert seeded.get(f"{P}/cases?ado=abc", headers=auth()).status_code == 422


def key_of(feature_name, path, scenario):
    return make_test_key(feature_name, path, scenario)


def test_search_includes_only_the_given_keys(seeded, auth):
    body = {"test_keys": [key_of("Hotel", "tests/features/hotel/a.feature", "h1")], "keys_mode": "include"}
    assert titles(seeded.post(f"{P}/cases/search", json=body, headers=auth())) == ["h1"]


def test_search_exclude_keeps_unlinked_cases(seeded, auth):
    body = {"test_keys": [key_of("Hotel", "tests/features/hotel/a.feature", "h1")], "keys_mode": "exclude",
            "folder": None}
    got = titles(seeded.post(f"{P}/cases/search", json=body, headers=auth()))
    assert "h1" not in got and "manual" in got and "b1" in got


def test_exclude_with_no_keys_returns_everything(seeded, auth):
    got = titles(seeded.post(f"{P}/cases/search", json={"test_keys": [], "keys_mode": "exclude"}, headers=auth()))
    assert len(got) == 6


def test_include_with_no_keys_returns_nothing(seeded, auth):
    assert titles(seeded.post(f"{P}/cases/search", json={"test_keys": [], "keys_mode": "include"}, headers=auth())) == []


def test_search_combines_with_other_filters_and_pages(seeded, auth):
    r = seeded.post(f"{P}/cases/search", json={"test_keys": [], "keys_mode": "exclude", "folder": "tests/features/hotels",
                                              "limit": 1, "offset": 0}, headers=auth())
    assert r.json()["total"] == 2 and len(r.json()["items"]) == 1


def test_search_rejects_too_many_keys(seeded, auth):
    r = seeded.post(f"{P}/cases/search", json={"test_keys": ["a" * 64] * 20001}, headers=auth())
    assert r.status_code == 422


def test_folder_facet_counts_subfolders_and_skips_archived(seeded, auth):
    number = seeded.get(f"{P}/cases?feature=Hotel", headers=auth()).json()["items"][0]["number"]  # h1
    assert seeded.patch(f"{P}/cases/{number}", json={"status": "archived"}, headers=auth()).status_code == 200
    rows = {r["path"]: r["count"] for r in seeded.get(f"{P}/case-folders", headers=auth()).json()}
    assert rows["tests"] == 4 and rows["tests/features"] == 4
    assert rows["tests/features/hotels"] == 2 and rows["tests/features/hotels/booking"] == 2
    assert "tests/features/hotel" not in rows


def test_feature_facet(seeded, auth):
    rows = seeded.get(f"{P}/case-features", headers=auth()).json()
    assert rows == sorted(rows, key=lambda r: r["feature"])
    assert {"feature": "Hotels booking", "count": 2} in rows


def test_viewers_can_read_the_facets_and_search(client, auth, project_role):
    project_role("viewer")
    assert client.get(f"{P}/case-folders", headers=auth()).status_code == 200
    assert client.get(f"{P}/case-features", headers=auth()).status_code == 200
    assert client.post(f"{P}/cases/search", json={}, headers=auth()).status_code == 200
