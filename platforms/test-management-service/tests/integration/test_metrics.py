import pytest

from src.casebook.utils import metrics

CASES = "/api/v1/projects/1/cases"
IMPORT = "/api/v1/projects/1/cases/import"
FEATURE = "Feature: A\n  Scenario: one\n    Given x\n  Scenario: two\n    Given y\n"


@pytest.fixture
def member(project_role):
    project_role("member")


def created(kind):
    return metrics.REGISTRY.get_sample_value("test_case_creation_total", {"type": kind}) or 0.0


def test_metrics_answer_and_count_requests_by_template(client):
    client.get("/api/v1/no-such-route/42")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "api_requests_total" in response.text
    assert 'service="test-management"' in response.text
    assert 'endpoint="unmatched"' in response.text


def test_both_case_creation_series_exist_before_any_case(client):
    text = client.get("/metrics").text
    assert 'test_case_creation_total{type="manual"}' in text
    assert 'test_case_creation_total{type="api"}' in text


def test_a_case_created_by_a_person_counts_as_manual(client, auth, member):
    before = created("manual")
    assert client.post(CASES, json={"title": "Pays with a stored card"}, headers=auth()).status_code == 201
    assert created("manual") == before + 1


def test_an_applied_import_counts_its_created_cases_as_api_and_a_dry_run_counts_nothing(client, auth, member):
    before = created("api")
    body = {"files": [{"path": "a.feature", "content": FEATURE}]}
    assert client.post(f"{IMPORT}?dry_run=true", json=body, headers=auth()).status_code == 200
    assert created("api") == before
    assert client.post(IMPORT, json=body, headers=auth()).status_code == 200
    assert created("api") == before + 2
