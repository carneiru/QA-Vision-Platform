"""Reading a run checks access through project-service over HTTP; the run's
database read must not keep a transaction (and a pooled connection) open
while that call waits."""
from datetime import datetime, timedelta, timezone

import httpx

from tests.conftest import PROJECT_URL, project_body
from src.ingestion.core.config import settings


def test_run_detail_checks_access_with_no_open_transaction(client, auth, db, http, make_key):
    _, key = make_key(project_id=1)
    now = datetime.now(timezone.utc)
    body = {
        "run": {"ci_provider": "local", "started_at": (now - timedelta(seconds=5)).isoformat(),
                "finished_at": now.isoformat()},
        "results": [{"name": "t", "status": "passed"}],
    }
    run_id = client.post("/api/v1/collect/runs", json=body, headers={"Authorization": f"Bearer {key}"}).json()["id"]

    seen = []

    def handler(request):
        seen.append(db.in_transaction())
        return httpx.Response(200, json=project_body(1, 10, "owner"))

    http.get(PROJECT_URL.format(base=settings.PROJECT_SERVICE_URL, project_id=1)).mock(side_effect=handler)

    response = client.get(f"/api/v1/runs/{run_id}", headers=auth())
    assert response.status_code == 200, response.text
    assert seen == [False]
    assert response.json()["results"][0]["name"] == "t"
