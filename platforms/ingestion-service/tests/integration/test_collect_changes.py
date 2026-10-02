"""Optional code-change data on an upload: stored per run, echoed by the run
read API. Absent changes mean "not reported", never zero."""

from datetime import datetime, timedelta, timezone

from src.ingestion.models.changes import RunChangedFile

URL = "/api/v1/collect/runs"


def upload_body(changes=None):
    now = datetime.now(timezone.utc)
    body = {
        "run": {"ci_provider": "github_actions", "branch": "main", "commit_sha": "3f2a9c1",
                "started_at": (now - timedelta(seconds=30)).isoformat(),
                "finished_at": now.isoformat()},
        "results": [{"suite": "s", "class_name": "C", "name": "t", "status": "passed", "duration_ms": 5}],
    }
    if changes is not None:
        body["changes"] = changes
    return body


CHANGES = {
    "base_ref": "origin/main",
    "truncated": False,
    "files": [
        {"path": "src/app.py", "status": "M", "additions": 12, "deletions": 3},
        {"path": "assets/logo.png", "status": "A", "additions": None, "deletions": None},
    ],
}


def test_changes_are_stored_and_summarized(client, make_key, db):
    _, key = make_key(project_id=1)
    response = client.post(URL, json=upload_body(CHANGES), headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["change_base_ref"] == "origin/main"
    assert body["changed_files"] == 2
    assert body["additions"] == 12
    assert body["deletions"] == 3
    assert body["changes_truncated"] is False

    rows = db.query(RunChangedFile).filter_by(run_id=body["id"]).all()
    assert {(r.path, r.status, r.additions, r.deletions) for r in rows} == {
        ("src/app.py", "M", 12, 3),
        ("assets/logo.png", "A", None, None),
    }


def test_run_detail_returns_the_changed_files(client, auth, make_key, project_role):
    project_role()
    _, key = make_key(project_id=1)
    created = client.post(URL, json=upload_body(CHANGES), headers={"Authorization": f"Bearer {key}"})
    run_id = created.json()["id"]

    detail = client.get(f"/api/v1/runs/{run_id}", headers=auth())
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["change_base_ref"] == "origin/main"
    assert [(f["path"], f["status"]) for f in body["changes"]] == [
        ("src/app.py", "M"), ("assets/logo.png", "A"),
    ]


def test_upload_without_changes_reports_nulls(client, auth, make_key, project_role):
    project_role()
    _, key = make_key(project_id=1)
    created = client.post(URL, json=upload_body(), headers={"Authorization": f"Bearer {key}"})
    assert created.status_code == 201
    body = created.json()
    assert body["change_base_ref"] is None
    assert body["changed_files"] is None
    assert body["additions"] is None
    assert body["changes_truncated"] is None

    detail = client.get(f"/api/v1/runs/{body['id']}", headers=auth())
    assert detail.json()["changes"] == []


def test_invalid_change_payloads_are_422(client, make_key):
    _, key = make_key(project_id=1)
    headers = {"Authorization": f"Bearer {key}"}

    bad_status = {"files": [{"path": "a", "status": "X"}]}
    assert client.post(URL, json=upload_body(bad_status), headers=headers).status_code == 422

    too_many = {"files": [{"path": f"f{i}", "status": "M"} for i in range(1001)]}
    assert client.post(URL, json=upload_body(too_many), headers=headers).status_code == 422

    nul_path = {"files": [{"path": "a\x00b", "status": "M"}]}
    assert client.post(URL, json=upload_body(nul_path), headers=headers).status_code == 422
