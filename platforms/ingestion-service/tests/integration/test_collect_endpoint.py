from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.models import Run, RunResult
from src.ingestion.utils import metrics

URL = "/api/v1/collect/runs"


def upload_body(results=None, **run):
    now = datetime.now(timezone.utc)
    meta = {"ci_provider": "github_actions", "branch": "main", "commit_sha": "3f2a9c1",
            "started_at": (now - timedelta(seconds=30)).isoformat(), "finished_at": now.isoformat()}
    meta.update(run)
    return {"run": meta, "results": results if results is not None else [
        {"suite": "checkout", "class_name": "CartTest", "name": "adds item", "status": "passed", "duration_ms": 5},
        {"suite": "checkout", "class_name": "CartTest", "name": "removes item", "status": "failed",
         "message": "expected 1", "details": "Traceback"},
        {"name": "flaky one", "status": "error"},
        {"name": "later", "status": "skipped"},
    ]}


def key_headers(key, idem=None):
    headers = {"Authorization": f"Bearer {key}"}
    if idem is not None:
        headers["Idempotency-Key"] = idem
    return headers


def rejected(reason):
    return metrics.REGISTRY.get_sample_value("qav_ingest_rejected_total", {"reason": reason}) or 0.0


def test_upload_is_stored_with_server_computed_counts(client, make_key, db):
    row, key = make_key(project_id=7)
    response = client.post(URL, json=upload_body(), headers=key_headers(key))
    assert response.status_code == 201
    body = response.json()
    assert (body["project_id"], body["total"], body["passed"], body["failed"], body["skipped"], body["errored"]) \
        == (7, 4, 1, 1, 1, 1)
    run = db.get(Run, body["id"])
    assert run.api_key_id == row.id and run.duration_ms >= 29_000
    statuses = {r.name: r.status for r in db.query(RunResult).filter_by(run_id=run.id)}
    assert statuses["flaky one"] == "errored"


def test_upload_never_calls_another_service(client, make_key, http):
    _, key = make_key()
    assert client.post(URL, json=upload_body(), headers=key_headers(key)).status_code == 201
    assert not http.calls


def test_last_used_at_is_set(client, make_key, db):
    row, key = make_key()
    client.post(URL, json=upload_body(), headers=key_headers(key))
    db.refresh(row)
    assert row.last_used_at is not None


@pytest.mark.parametrize("header", [None, "Bearer", "Bearer ", "Bearer not-a-qeos-key", "Basic dXNlcjpwdw=="])
def test_missing_or_malformed_key_is_401(client, header):
    headers = {} if header is None else {"Authorization": header}
    response = client.post(URL, json=upload_body(), headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_unknown_key_is_401(client, db):
    assert client.post(URL, json=upload_body(), headers=key_headers("qeos_" + "A" * 43)).status_code == 401


def test_legacy_qav_key_still_authenticates(client, db):
    """Keys issued before the QEOS rename start with qav_ and keep working."""
    from src.ingestion.models import ApiKey
    from src.ingestion.utils.keys import display_prefix, hash_key

    legacy = "qav_" + "L" * 43
    db.add(ApiKey(project_id=1, organization_id=10, name="old", key_prefix=display_prefix(legacy),
                  key_hash=hash_key(legacy), created_by=1))
    db.commit()
    assert client.post(URL, json=upload_body(), headers=key_headers(legacy)).status_code == 201


def test_unknown_legacy_key_is_401(client, db):
    assert client.post(URL, json=upload_body(), headers=key_headers("qav_" + "A" * 43)).status_code == 401


def test_revoked_key_is_401(client, make_key):
    _, key = make_key(revoked=True)
    assert client.post(URL, json=upload_body(), headers=key_headers(key)).status_code == 401


def test_invalid_key_and_invalid_body_is_401_not_422(client):
    response = client.post(URL, json={"nonsense": True}, headers=key_headers("qeos_" + "B" * 43))
    assert response.status_code == 401


def test_a_key_writes_only_into_its_own_project(client, make_key, db):
    _, key = make_key(project_id=5)
    body = client.post(URL, json=upload_body(), headers=key_headers(key)).json()
    assert db.get(Run, body["id"]).project_id == 5


def test_idempotent_replay_returns_the_same_run_once(client, make_key, db):
    _, key = make_key()
    payload = upload_body()
    first = client.post(URL, json=payload, headers=key_headers(key, "ci-run-123"))
    second = client.post(URL, json=payload, headers=key_headers(key, "ci-run-123"))
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert db.query(Run).count() == 1


def test_same_idempotency_key_different_payload_is_409(client, make_key, db):
    _, key = make_key()
    client.post(URL, json=upload_body(), headers=key_headers(key, "ci-run-123"))
    before = rejected("conflict")
    response = client.post(URL, json=upload_body(branch="other"), headers=key_headers(key, "ci-run-123"))
    assert response.status_code == 409
    assert response.json() == {"detail": "Idempotency-Key reused with a different payload"}
    assert rejected("conflict") == before + 1
    assert db.query(Run).count() == 1


def test_same_idempotency_key_in_another_project_is_independent(client, make_key, db):
    _, key_a = make_key(project_id=1)
    _, key_b = make_key(project_id=2)
    assert client.post(URL, json=upload_body(), headers=key_headers(key_a, "same")).status_code == 201
    assert client.post(URL, json=upload_body(), headers=key_headers(key_b, "same")).status_code == 201


def test_without_idempotency_key_every_upload_is_new(client, make_key, db):
    _, key = make_key()
    payload = upload_body()
    client.post(URL, json=payload, headers=key_headers(key))
    client.post(URL, json=payload, headers=key_headers(key))
    assert db.query(Run).count() == 2


@pytest.mark.parametrize("idem", ["", "has space", "x" * 256, "tab\there"])
def test_invalid_idempotency_key_is_422(client, make_key, idem):
    _, key = make_key()
    assert client.post(URL, json=upload_body(), headers=key_headers(key, idem)).status_code == 422


def test_azure_pipelines_runs_are_accepted(client, make_key, db):
    _, key = make_key()
    response = client.post(URL, json=upload_body(ci_provider="azure_pipelines"), headers=key_headers(key))
    assert response.status_code == 201, response.text
    assert db.query(Run).one().ci_provider == "azure_pipelines"


def test_invalid_payload_is_422_and_counted(client, make_key, db):
    _, key = make_key()
    before = rejected("validation")
    response = client.post(URL, json=upload_body(ci_provider="travis"), headers=key_headers(key))
    assert response.status_code == 422
    assert rejected("validation") == before + 1
    assert db.query(Run).count() == 0


def test_auth_rejection_is_counted(client):
    before = rejected("auth")
    client.post(URL, json=upload_body(), headers=key_headers("qeos_" + "C" * 43))
    assert rejected("auth") == before + 1


def test_success_counters_move(client, make_key):
    _, key = make_key()
    runs = metrics.REGISTRY.get_sample_value("qav_ingest_runs_total") or 0.0
    results = metrics.REGISTRY.get_sample_value("qav_ingest_results_total") or 0.0
    client.post(URL, json=upload_body(), headers=key_headers(key))
    assert metrics.REGISTRY.get_sample_value("qav_ingest_runs_total") == runs + 1
    assert metrics.REGISTRY.get_sample_value("qav_ingest_results_total") == results + 4


def test_long_text_is_stored_truncated_and_flagged(client, make_key, db):
    from src.ingestion.core.config import settings

    _, key = make_key()
    results = [{"name": "big", "status": "failed", "details": "é" * settings.MAX_TEXT_BYTES}]
    body = client.post(URL, json=upload_body(results=results), headers=key_headers(key)).json()
    stored = db.query(RunResult).filter_by(run_id=body["id"]).one()
    assert stored.truncated is True
    assert len(stored.details.encode("utf-8")) <= settings.MAX_TEXT_BYTES


def test_a_failed_write_stores_nothing(client, make_key, db, monkeypatch):
    from src.ingestion.service import ingest_service

    _, key = make_key()

    def explode(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(ingest_service, "test_key", explode)
    with pytest.raises(RuntimeError):
        client.post(URL, json=upload_body(), headers=key_headers(key))
    db.rollback()
    assert db.query(Run).count() == 0
