"""POST /analytics/report: validation, roles, isolation, envelope, timeout (spec: ingestion section)."""
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from src.ingestion.service import report_service
from conftest import REPORT_URL, post_report, report_key

ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")
KEY = "a" * 64


@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_project_role_reads_the_report(client, auth, project_role, report_now, role):
    project_role(role)
    assert post_report(client, auth).status_code == 200


def test_a_non_member_gets_404_and_no_token_401(client, auth, project_role, report_now):
    project_role(status_code=404, body={"detail": "Project not found"})
    assert post_report(client, auth).status_code == 404
    project_role(exc=httpx.ConnectError("refused"))
    assert post_report(client, auth).status_code == 503
    assert client.post(REPORT_URL, json={"from": "2026-10-01", "to": "2026-10-07", "sections": ["summary"]}).status_code == 401


@pytest.mark.parametrize("body,detail", [
    ({"from": "2026-10-07", "to": "2026-10-01"}, "from must be on or before to"),
    ({"from": "2026-06-01", "to": "2026-10-01"}, "at most 90"),
    ({"from": "2025-08-01", "to": "2025-08-05"}, "more than 400 days ago"),
    ({"to": "2026-10-20"}, "to is in the future"),
    ({"tz": "America"}, "Unknown time zone"),
])
def test_period_and_zone_rules_are_422_with_the_rule(client, auth, project_role, report_now, body, detail):
    project_role()
    response = post_report(client, auth, **body)
    assert response.status_code == 422
    assert detail in str(response.json()["detail"])


@pytest.mark.parametrize("body", [
    {"test_keys": []},
    {"test_keys": ["not-hex"]},
    {"test_keys": [KEY] * 20001},
    {"origin": "qeos"},
    {"origin": "ci", "requested_run_urls": ["https://github.com/a/b/actions/runs/1"] * 5001},
    {"origin": "ci", "requested_run_urls": ["x" * 2049]},
    {"sections": []},
    {"sections": ["summary", "summary"]},
    {"sections": ["everything"]},
    {"ci_provider": "travis"},
    {"branch": "b" * 256},
    {"environment": "e" * 101},
    {"branch": "a\u0000b"},
    {"bucket": "month"},
    {"surprise": 1},
])
def test_bad_bodies_are_422(client, auth, project_role, report_now, body):
    project_role()
    assert post_report(client, auth, **body).status_code == 422


def test_origin_without_urls_says_so(client, auth, project_role, report_now):
    project_role()
    response = post_report(client, auth, origin="ci")
    assert "requested_run_urls is required with origin" in str(response.json()["detail"])


def test_the_envelope_has_the_periods_scope_and_only_the_asked_sections(client, auth, project_role, report_now):
    project_role("viewer")
    body = post_report(client, auth, tz="Europe/Lisbon", test_keys=[KEY.upper(), KEY]).json()
    assert body["period"] == {"from": "2026-10-01", "to": "2026-10-07", "days": 7,
                              "start": "2026-09-30T23:00:00Z", "end": "2026-10-07T23:00:00Z"}
    assert body["previous_period"]["from"] == "2026-09-24" and body["previous_period"]["to"] == "2026-09-30"
    assert body["tz"] == "Europe/Lisbon" and body["bucket"] == "day"
    assert body["generated_at"] == "2026-10-08T12:00:00Z"
    assert body["scope"] == {"runs": 0, "previous_runs": 0, "test_keys": 1}  # duplicates and case removed
    assert set(body) == {"period", "previous_period", "tz", "bucket", "generated_at", "scope", "summary"}


def test_a_long_period_buckets_by_week(client, auth, project_role, report_now):
    project_role()
    assert post_report(client, auth, **{"from": "2026-08-01", "to": "2026-10-07"}).json()["bucket"] == "week"
    assert post_report(client, auth, **{"from": "2026-08-01", "to": "2026-10-07", "bucket": "day"}).json()["bucket"] == "day"


def test_another_projects_runs_never_count(client, auth, project_role, report_now, seed_run):
    project_role()
    seed_run(datetime(2026, 10, 3, 10, tzinfo=timezone.utc), project_id=2)
    seed_run(datetime(2026, 9, 26, 10, tzinfo=timezone.utc), project_id=2)
    assert post_report(client, auth).json()["scope"] == {"runs": 0, "previous_runs": 0, "test_keys": None}


def test_runs_count_by_period(client, auth, project_role, report_now, seed_run):
    project_role()
    seed_run(datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc))      # first instant of the period
    seed_run(datetime(2026, 10, 7, 23, 59, tzinfo=timezone.utc))
    seed_run(datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc))      # end is exclusive
    seed_run(datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc))      # previous period
    seed_run(datetime(2026, 9, 23, 23, 59, tzinfo=timezone.utc))    # before both
    assert post_report(client, auth).json()["scope"] == {"runs": 2, "previous_runs": 1, "test_keys": None}


class _Cancelled(Exception):
    sqlstate = "57014"  # PostgreSQL query_canceled: what statement_timeout raises


def test_a_statement_timeout_is_503_report_timeout(client, auth, project_role, report_now, monkeypatch):
    project_role()

    def slow(*args, **kwargs):
        raise OperationalError("SELECT ...", {}, _Cancelled("canceling statement due to statement timeout"))

    monkeypatch.setattr(report_service, "build_report", slow)
    response = post_report(client, auth)
    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "report_timeout",
                                         "message": "This report took too long. Narrow the period or the filters."}


def test_other_database_errors_are_not_disguised_as_timeouts():
    assert not report_service.is_timeout(OperationalError("x", {}, Exception("disk full")))
    assert report_service.is_timeout(OperationalError("x", {}, _Cancelled()))


def test_the_handler_ends_its_transaction(client, auth, project_role, report_now, db):
    project_role()
    assert post_report(client, auth).status_code == 200
    assert not db.in_transaction()


GH = "https://github.com/acme/obt/actions/runs/"


def runs_of(client, auth, **body):
    response = post_report(client, auth, **body)
    assert response.status_code == 200, response.text
    return response.json()["scope"]["runs"]


def test_each_run_filter_alone_and_combined(client, auth, project_role, report_now, seed_run):
    project_role()
    day = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    seed_run(day, branch="main", environment="staging", ci_provider="github_actions")
    seed_run(day, branch="main", environment="prod", ci_provider="jenkins")
    seed_run(day, branch="dev", environment="staging", ci_provider="jenkins")
    assert runs_of(client, auth) == 3
    assert runs_of(client, auth, branch="main") == 2
    assert runs_of(client, auth, branch="") == 3                  # empty means no filter
    assert runs_of(client, auth, environment="staging") == 2
    assert runs_of(client, auth, ci_provider="jenkins") == 2
    assert runs_of(client, auth, branch="main", environment="staging", ci_provider="jenkins") == 0


def test_origin_matches_the_play_url_without_regard_to_case_on_github_only(client, auth, project_role, report_now, seed_run):
    project_role()
    day = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    seed_run(day, ci_provider="github_actions", ci_run_url=GH + "7")                   # requested from QEOS
    seed_run(day, ci_provider="github_actions", ci_run_url=GH + "7")                   # a shard of the same Play
    seed_run(day, ci_provider="github_actions", ci_run_url=GH + "8")                   # CI
    seed_run(day, ci_provider="local", ci_run_url=GH + "7")                            # not GitHub: CI
    seed_run(day, ci_provider="github_actions", ci_run_url=None)                       # CI
    seed_run(day, ci_provider="github_actions", ci_run_url=GH + "7/")                  # trailing slash: another URL
    urls = [(GH + "7").upper()]
    assert runs_of(client, auth, origin="qeos", requested_run_urls=urls) == 2
    assert runs_of(client, auth, origin="ci", requested_run_urls=urls) == 4
    assert runs_of(client, auth, origin="any", requested_run_urls=urls) == 6        # ignored with any
    assert runs_of(client, auth, origin="qeos", requested_run_urls=[]) == 0
    assert runs_of(client, auth, origin="ci", requested_run_urls=[]) == 6


def test_test_keys_count_only_runs_with_a_result_for_them(client, auth, project_role, report_now, seed_run):
    project_role()
    day = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    seed_run(day, results=(("t1", "passed", 1), ("t2", "failed", 1)))
    seed_run(day, results=(("t1", "passed", 1),))
    seed_run(datetime(2026, 9, 26, tzinfo=timezone.utc), results=(("t2", "passed", 1),))
    scope = post_report(client, auth, test_keys=[report_key("t2").upper()]).json()["scope"]
    assert scope == {"runs": 1, "previous_runs": 1, "test_keys": 1}
