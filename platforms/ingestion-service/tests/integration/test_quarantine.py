"""Quarantine: a quarantined (muted) test still runs and is still shown, but its failures do not
decide the run's verdict, raise a failure alert or fail the CI gate."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.ingestion.core.config import settings
from src.ingestion.models import MutedTest
from src.ingestion.models.notification_channel import NotificationChannel
from src.ingestion.service.ingest_service import test_key as key_of
from src.ingestion.utils import notify_targets

SLACK = "https://hooks.slack.com/services/T000/B000/XXXXXXXXXXXXXXXXXXXXabcd"


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(notify_targets, "resolve", lambda host: ["93.184.216.34"])
    monkeypatch.setattr(settings, "DASHBOARD_URL", "https://qav.example.com")


def quarantine(db, *names, project_id=1):
    for name in names:
        db.add(MutedTest(project_id=project_id, test_key=key_of("checkout", "Cart", name), muted_by_user_id=1))
    db.commit()


def upload(client, key, outcomes):
    now = datetime.now(timezone.utc)
    body = {"run": {"ci_provider": "local", "branch": "main", "started_at": (now - timedelta(seconds=5)).isoformat(),
                    "finished_at": now.isoformat()},
            "results": [{"suite": "checkout", "class_name": "Cart", "name": name, "status": status, "duration_ms": 1,
                         "message": f"{name} broke" if status != "passed" else None}
                        for name, status in outcomes.items()]}
    response = client.post("/api/v1/collect/runs", json=body, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 201, response.text
    return response.json()


def test_the_upload_receipt_separates_blocking_from_quarantined_failures(client, db, make_key):
    _, key = make_key(project_id=1)
    quarantine(db, "flaky one")
    receipt = upload(client, key, {"flaky one": "failed", "real bug": "errored", "fine": "passed"})
    assert (receipt["failed"], receipt["errored"], receipt["quarantined"], receipt["blocking"]) == (1, 1, 1, 1)
    receipt = upload(client, key, {"flaky one": "failed", "fine": "passed"})
    assert (receipt["quarantined"], receipt["blocking"]) == (1, 0)


def test_another_projects_quarantine_does_not_apply(client, db, make_key):
    _, key = make_key(project_id=1)
    quarantine(db, "flaky one", project_id=2)
    assert upload(client, key, {"flaky one": "failed"})["blocking"] == 1


def test_run_detail_and_failure_groups_mark_quarantined_tests(client, db, make_key, auth, project_role):
    _, key = make_key(project_id=1)
    quarantine(db, "flaky one")
    run_id = upload(client, key, {"flaky one": "failed", "real bug": "failed", "fine": "passed"})["id"]
    project_role("viewer")
    detail = client.get(f"/api/v1/runs/{run_id}", headers=auth()).json()
    assert (detail["quarantined"], detail["blocking"]) == (1, 1)
    assert {r["name"]: r["quarantined"] for r in detail["results"]} == {"flaky one": True, "real bug": False, "fine": False}
    groups = client.get(f"/api/v1/runs/{run_id}/failure-groups", headers=auth()).json()
    assert (groups["quarantined"], groups["blocking"]) == (1, 1)
    by_test = {t["name"]: t["quarantined"] for g in groups["groups"] for t in g["tests"]}
    assert by_test == {"flaky one": True, "real bug": False}
    assert {g["headline"]: g["quarantined"] for g in groups["groups"]} == {"flaky one broke": 1, "real bug broke": 0}


def test_a_run_failing_only_in_quarantine_raises_no_alert(client, db, make_key, http):
    _, key = make_key(project_id=1)
    quarantine(db, "flaky one")
    db.add(NotificationChannel(project_id=1, name="QA", kind="slack", url=SLACK, enabled=True))
    db.commit()
    route = http.post(SLACK).mock(return_value=httpx.Response(200))
    upload(client, key, {"flaky one": "failed", "fine": "passed"})
    assert route.call_count == 0
    upload(client, key, {"flaky one": "failed", "real bug": "failed"})
    assert route.call_count == 1
    text = route.calls.last.request.content.decode()
    assert "1 of 2 tests failed" in text and "1 quarantined" in text
    assert "real bug" in text and "flaky one" not in text
