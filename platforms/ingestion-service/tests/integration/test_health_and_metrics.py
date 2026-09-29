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
