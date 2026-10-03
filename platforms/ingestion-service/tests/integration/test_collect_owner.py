"""Optional owner (from CODEOWNERS) per result: stored and echoed by the run
read API. Absent means "not reported"."""

from datetime import datetime, timedelta, timezone

URL = "/api/v1/collect/runs"


def upload_body(owner=None):
    now = datetime.now(timezone.utc)
    result = {"suite": "s", "class_name": "C", "name": "t", "status": "passed",
              "duration_ms": 5, "file": "tests/test_x.py"}
    if owner is not None:
        result["owner"] = owner
    return {
        "run": {"ci_provider": "github_actions", "branch": "main", "commit_sha": "3f2a9c1",
                "started_at": (now - timedelta(seconds=30)).isoformat(),
                "finished_at": now.isoformat()},
        "results": [result],
    }


def test_owner_is_stored_and_returned(client, auth, make_key, project_role):
    project_role()
    _, key = make_key(project_id=1)
    created = client.post(URL, json=upload_body("@org/qa-team @alice@example.com"),
                          headers={"Authorization": f"Bearer {key}"})
    assert created.status_code == 201, created.text

    detail = client.get(f"/api/v1/runs/{created.json()['id']}", headers=auth())
    assert detail.json()["results"][0]["owner"] == "@org/qa-team @alice@example.com"


def test_absent_owner_is_null(client, auth, make_key, project_role):
    project_role()
    _, key = make_key(project_id=1)
    created = client.post(URL, json=upload_body(), headers={"Authorization": f"Bearer {key}"})
    assert created.status_code == 201

    detail = client.get(f"/api/v1/runs/{created.json()['id']}", headers=auth())
    assert detail.json()["results"][0]["owner"] is None


def test_unstorable_owner_is_422(client, make_key):
    _, key = make_key(project_id=1)
    response = client.post(URL, json=upload_body("a\x00b"), headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 422
