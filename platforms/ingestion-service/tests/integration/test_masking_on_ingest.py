from datetime import datetime, timedelta, timezone

from src.ingestion.core.config import settings
from src.ingestion.models import Run, RunResult
from src.ingestion.utils import metrics

URL = "/api/v1/collect/runs"
GH = "ghp_" + "A1b2C3d4E5" * 3 + "F6g7H8"


def body(results, **run):
    now = datetime.now(timezone.utc)
    meta = {"ci_provider": "local", "started_at": (now - timedelta(seconds=5)).isoformat(), "finished_at": now.isoformat()}
    meta.update(run)
    return {"run": meta, "results": results}


def headers(key, idem=None):
    h = {"Authorization": f"Bearer {key}"}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def stored(db, run_id):
    return db.query(RunResult).filter_by(run_id=run_id).order_by(RunResult.id).all()


def redactions(kind):
    return metrics.REGISTRY.get_sample_value("qav_ingest_redactions_total", {"kind": kind}) or 0.0


def test_a_secret_in_the_output_is_never_stored(client, make_key, db):
    _, key = make_key()
    leak = {"name": "login", "status": "failed", "message": "login failed for ann@acme.test",
            "details": f"Authorization: Bearer abc.def\npassword=hunter2\n{GH}"}
    response = client.post(URL, json=body([leak]), headers=headers(key))
    assert response.status_code == 201
    [row] = stored(db, response.json()["id"])
    assert row.message == "login failed for [REDACTED:email]"
    for secret in ("abc.def", "hunter2", GH, "ann@acme.test"):
        assert secret not in row.details + row.message
    assert "[REDACTED:authorization]" in row.details and "[REDACTED:github_token]" in row.details
    assert row.redacted is True


def test_a_clean_result_is_not_flagged(client, make_key, db):
    _, key = make_key()
    response = client.post(URL, json=body([{"name": "ok", "status": "failed", "message": "expected 1, got 2"}]),
                           headers=headers(key))
    [row] = stored(db, response.json()["id"])
    assert row.redacted is False and row.message == "expected 1, got 2"


def test_masking_happens_before_truncation(client, make_key, db):
    _, key = make_key()
    # The token straddles the 64 KB cut: truncating first would keep its first half
    details = "x" * (settings.MAX_TEXT_BYTES - 16) + " " + GH
    response = client.post(URL, json=body([{"name": "big", "status": "failed", "details": details}]),
                           headers=headers(key))
    [row] = stored(db, response.json()["id"])
    assert "ghp_" not in row.details
    assert row.truncated is True and row.redacted is True
    assert len(row.details.encode("utf-8")) <= settings.MAX_TEXT_BYTES


def test_a_password_in_the_ci_run_url_is_masked(client, make_key, db):
    _, key = make_key()
    response = client.post(URL, json=body([{"name": "t", "status": "passed"}],
                                          ci_run_url="https://bob:s3cret@ci.acme.test/job/1"), headers=headers(key))
    run = db.get(Run, response.json()["id"])
    assert run.ci_run_url == "https://bob:[REDACTED:url_password]@ci.acme.test/job/1"


def test_a_long_ci_run_url_stays_within_its_column(client, make_key, db):
    _, key = make_key()
    url = "https://bob:x@ci.acme.test/" + "a" * (2048 - len("https://bob:x@ci.acme.test/"))
    response = client.post(URL, json=body([{"name": "t", "status": "passed"}], ci_run_url=url), headers=headers(key))
    assert response.status_code == 201
    run = db.get(Run, response.json()["id"])
    assert len(run.ci_run_url) == 2048
    assert run.ci_run_url.startswith("https://bob:[REDACTED:url_password]@ci.acme.test/")


def test_a_replay_still_matches_the_stored_run(client, make_key):
    _, key = make_key()
    upload = body([{"name": "t", "status": "failed", "details": "password=hunter2"}])
    first = client.post(URL, json=upload, headers=headers(key, "job-1"))
    second = client.post(URL, json=upload, headers=headers(key, "job-1"))
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]


def test_the_metric_counts_results_by_kind(client, make_key):
    _, key = make_key()
    before_password, before_github = redactions("password"), redactions("github_token")
    results = [
        {"name": "a", "status": "failed", "details": "password=x"},
        {"name": "b", "status": "failed", "message": "password=y", "details": f"password=z {GH}"},
        {"name": "c", "status": "passed"},
    ]
    assert client.post(URL, json=body(results), headers=headers(key)).status_code == 201
    assert redactions("password") - before_password == 2
    assert redactions("github_token") - before_github == 1


def test_the_read_api_shows_the_flag(client, make_key, auth, project_role):
    _, key = make_key(project_id=1)
    run_id = client.post(URL, json=body([{"name": "t", "status": "failed", "details": "password=x"}]),
                         headers=headers(key)).json()["id"]
    project_role("viewer", project_id=1)
    result = client.get(f"/api/v1/runs/{run_id}", headers=auth()).json()["results"][0]
    assert result["redacted"] is True and result["details"] == "password=[REDACTED:password]"
