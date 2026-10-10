def test_health_needs_no_token(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_metrics_are_prometheus_text(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    for name in ("qav_ingest_runs_total", "qav_ingest_results_total",
                 "qav_ingest_rejected_total", "qav_ingest_duration_seconds"):
        assert name in response.text


from src.ingestion.utils import metrics


def test_request_metrics_share_the_page_with_the_qav_metrics(client):
    client.get("/api/v1/no-such-route/42")
    text = client.get("/metrics").text
    line = next(ln for ln in text.splitlines() if ln.startswith("api_requests_total{"))
    for label in ('service="ingestion"', 'endpoint="unmatched"', 'method="GET"', 'status_code="404"'):
        assert label in line
    assert "qav_ingest_runs_total" in text and "build_info" in text


def test_the_four_execution_series_exist_before_any_upload(client):
    text = client.get("/metrics").text
    for status in ("passed", "failed", "errored", "skipped"):
        assert f'test_executions_total{{status="{status}"}}' in text


def executions(status):
    return metrics.REGISTRY.get_sample_value("test_executions_total", {"status": status}) or 0.0


def test_each_stored_result_counts_once_by_status_and_a_replay_counts_nothing(client, make_key):
    _, key = make_key(project_id=7)
    before = {s: executions(s) for s in ("passed", "failed", "errored", "skipped")}
    body = {"run": {"ci_provider": "local", "started_at": "2026-10-10T10:00:00+00:00",
                    "finished_at": "2026-10-10T10:00:05+00:00"},
            "results": [{"name": "a", "status": "passed"}, {"name": "b", "status": "passed"},
                        {"name": "c", "status": "failed"}, {"name": "d", "status": "error"},
                        {"name": "e", "status": "skipped"}]}
    headers = {"Authorization": f"Bearer {key}", "Idempotency-Key": "exec-1"}
    assert client.post("/api/v1/collect/runs", json=body, headers=headers).status_code == 201
    assert client.post("/api/v1/collect/runs", json=body, headers=headers).status_code == 200
    assert {s: executions(s) - before[s] for s in before} == {"passed": 2, "failed": 1, "errored": 1, "skipped": 1}
