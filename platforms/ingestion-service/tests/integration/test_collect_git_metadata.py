"""Optional git metadata on an upload: author, commit subject, PR number and
base branch, stored per run and echoed by the read API. Absent means null."""

from datetime import datetime, timedelta, timezone


def upload_body(**run_extra):
    now = datetime.now(timezone.utc)
    meta = {"ci_provider": "github_actions", "branch": "main", "commit_sha": "3f2a9c1",
            "started_at": (now - timedelta(seconds=30)).isoformat(),
            "finished_at": now.isoformat()}
    meta.update(run_extra)
    return {"run": meta,
            "results": [{"suite": "s", "class_name": "C", "name": "t", "status": "passed",
                         "duration_ms": 5}]}


META = {
    "commit_author": "Ada Lovelace",
    "commit_message": "fix(cart): keep totals stable under retries",
    "pr_number": 123,
    "base_branch": "main",
}


def test_git_metadata_is_stored_and_echoed(client, auth, make_key, project_role):
    project_role()
    _, key = make_key(project_id=1)
    created = client.post(URL := "/api/v1/collect/runs", json=upload_body(**META),
                          headers={"Authorization": f"Bearer {key}"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["commit_author"] == "Ada Lovelace"
    assert body["pr_number"] == 123

    detail = client.get(f"/api/v1/runs/{body['id']}", headers=auth())
    run = detail.json()
    assert run["commit_message"] == META["commit_message"]
    assert run["base_branch"] == "main"


def test_absent_metadata_is_null(client, make_key):
    _, key = make_key(project_id=1)
    created = client.post("/api/v1/collect/runs", json=upload_body(),
                          headers={"Authorization": f"Bearer {key}"})
    assert created.status_code == 201
    body = created.json()
    assert body["commit_author"] is None
    assert body["pr_number"] is None


def test_invalid_metadata_is_422(client, make_key):
    _, key = make_key(project_id=1)
    headers = {"Authorization": f"Bearer {key}"}
    assert client.post("/api/v1/collect/runs", json=upload_body(pr_number=-1),
                       headers=headers).status_code == 422
    assert client.post("/api/v1/collect/runs", json=upload_body(commit_author="a\x00b"),
                       headers=headers).status_code == 422


def test_a_secret_in_the_commit_subject_is_masked(client, db, make_key):
    from src.ingestion.models import Run
    from src.ingestion.models.masking_pattern import MaskingPattern

    _, key = make_key(project_id=1)
    db.add(MaskingPattern(project_id=1, name="ticket", pattern=r"JIRA-\d+"))
    db.commit()
    subject = "hotfix JIRA-77: rotate token=ghp_" + "a" * 36 + " for ana@example.com"
    created = client.post("/api/v1/collect/runs", json=upload_body(commit_message=subject),
                          headers={"Authorization": f"Bearer {key}"})
    assert created.status_code == 201, created.text
    stored = db.query(Run).one().commit_message
    assert "ghp_" not in stored and "ana@example.com" not in stored and "JIRA-77" not in stored
    assert stored.startswith("hotfix [REDACTED:ticket]: rotate token=[REDACTED:")
    assert len(stored) <= 500
