def test_metrics_answer_and_count_requests_by_template(client):
    client.get("/api/v1/no-such-route/42")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "api_requests_total" in response.text
    assert 'service="project"' in response.text
    assert 'endpoint="unmatched"' in response.text
    assert any(line.startswith("build_info{") and 'service="project"' in line for line in response.text.splitlines())
