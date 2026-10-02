"""Optional components-under-test on an upload: which repos/versions the run
exercised (e.g. the product build an E2E suite ran against). Stored per run,
echoed by the run read API. Absent components mean "not reported"."""

from datetime import datetime, timedelta, timezone

from src.ingestion.models.component import RunComponent

URL = "/api/v1/collect/runs"


def upload_body(components=None):
    now = datetime.now(timezone.utc)
    body = {
        "run": {"ci_provider": "github_actions", "branch": "main", "commit_sha": "3f2a9c1",
                "started_at": (now - timedelta(seconds=30)).isoformat(),
                "finished_at": now.isoformat()},
        "results": [{"suite": "s", "class_name": "C", "name": "t", "status": "passed", "duration_ms": 5}],
    }
    if components is not None:
        body["components"] = components
    return body


COMPONENTS = [
    {"name": "product-api", "sha": "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"},
    {"name": "web-frontend", "sha": "0f1e2d3c"},
]


def test_components_are_stored(client, make_key, db):
    _, key = make_key(project_id=1)
    response = client.post(URL, json=upload_body(COMPONENTS), headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 201, response.text

    rows = db.query(RunComponent).filter_by(run_id=response.json()["id"]).all()
    assert {(r.name, r.sha) for r in rows} == {
        ("product-api", "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"),
        ("web-frontend", "0f1e2d3c"),
    }


def test_run_detail_returns_the_components(client, auth, make_key, project_role):
    project_role()
    _, key = make_key(project_id=1)
    created = client.post(URL, json=upload_body(COMPONENTS), headers={"Authorization": f"Bearer {key}"})
    run_id = created.json()["id"]

    detail = client.get(f"/api/v1/runs/{run_id}", headers=auth())
    assert detail.status_code == 200, detail.text
    assert [(c["name"], c["sha"]) for c in detail.json()["components"]] == [
        ("product-api", "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"),
        ("web-frontend", "0f1e2d3c"),
    ]


def test_upload_without_components_reports_empty_list(client, auth, make_key, project_role):
    project_role()
    _, key = make_key(project_id=1)
    created = client.post(URL, json=upload_body(), headers={"Authorization": f"Bearer {key}"})
    assert created.status_code == 201

    detail = client.get(f"/api/v1/runs/{created.json()['id']}", headers=auth())
    assert detail.json()["components"] == []


def test_invalid_component_payloads_are_422(client, make_key):
    _, key = make_key(project_id=1)
    headers = {"Authorization": f"Bearer {key}"}

    bad_sha = [{"name": "api", "sha": "not-hex!"}]
    assert client.post(URL, json=upload_body(bad_sha), headers=headers).status_code == 422

    empty_name = [{"name": "", "sha": "0f1e2d3c"}]
    assert client.post(URL, json=upload_body(empty_name), headers=headers).status_code == 422

    duplicate_names = [{"name": "api", "sha": "0f1e2d3c"}, {"name": "api", "sha": "aa11bb22"}]
    assert client.post(URL, json=upload_body(duplicate_names), headers=headers).status_code == 422

    too_many = [{"name": f"c{i}", "sha": "0f1e2d3c"} for i in range(21)]
    assert client.post(URL, json=upload_body(too_many), headers=headers).status_code == 422

    nul_name = [{"name": "a\x00b", "sha": "0f1e2d3c"}]
    assert client.post(URL, json=upload_body(nul_name), headers=headers).status_code == 422
