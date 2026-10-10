"""qeos_shared.metrics: one call gives a service request metrics named after blueprint §11.2."""
import sys

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, Counter, generate_latest

from qeos_shared.metrics import install_metrics

CASE = "/api/v1/projects/{project_id}/cases/{number}"


def make_app(registry=None, **kwargs):
    app = FastAPI()
    holder = {}

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    @app.get(CASE)
    def case(project_id: int, number: int):
        return {"ok": True}

    @app.post("/api/v1/items")
    def create():
        raise HTTPException(status_code=409, detail="taken")

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    @app.get("/inflight")
    def inflight():
        return {"value": holder["registry"].get_sample_value("http_requests_in_flight", {"service": "svc"})}

    kwargs.setdefault("version", "1.2.3")
    kwargs.setdefault("commit", "abc1234")
    holder["registry"] = install_metrics(app, service="svc", registry=registry, **kwargs)
    return app, holder["registry"]


@pytest.fixture
def svc():
    app, registry = make_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, registry


def requests(registry, **labels):
    return registry.get_sample_value("api_requests_total", {"service": "svc", **labels}) or 0.0


def test_the_endpoint_label_is_the_route_template_never_the_raw_path(svc):
    client, registry = svc
    assert client.get("/api/v1/projects/7/cases/3").status_code == 200
    assert requests(registry, method="GET", endpoint=CASE, status_code="200") == 1
    assert "/projects/7" not in generate_latest(registry).decode()


def test_a_path_that_matches_no_route_is_unmatched(svc):
    client, registry = svc
    client.get("/wp-login.php")
    client.get("/api/v1/does-not-exist/12345")
    assert requests(registry, method="GET", endpoint="unmatched", status_code="404") == 2
    text = generate_latest(registry).decode()
    assert "wp-login" not in text and "12345" not in text


def test_the_status_code_is_the_exact_code(svc):
    client, registry = svc
    assert client.post("/api/v1/items").status_code == 409
    assert requests(registry, method="POST", endpoint="/api/v1/items", status_code="409") == 1


def test_a_known_route_with_the_wrong_method_keeps_its_template(svc):
    client, registry = svc
    assert client.get("/api/v1/items").status_code == 405
    assert requests(registry, method="GET", endpoint="/api/v1/items", status_code="405") == 1


def test_an_unknown_method_is_counted_as_other(svc):
    """Review Focus 1: a scanner's made-up methods must not create series."""
    client, registry = svc
    client.request("BREW", "/api/v1/items")
    assert requests(registry, method="other", endpoint="/api/v1/items", status_code="405") == 1
    assert 'method="BREW"' not in generate_latest(registry).decode()


def test_an_unhandled_exception_counts_as_500(svc):
    client, registry = svc
    assert client.get("/boom").status_code == 500
    assert requests(registry, method="GET", endpoint="/boom", status_code="500") == 1


def test_health_and_metrics_are_not_counted(svc):
    client, registry = svc
    client.get("/health")
    client.get("/metrics")
    text = generate_latest(registry).decode()
    assert 'endpoint="/health"' not in text and 'endpoint="/metrics"' not in text


def test_the_in_flight_gauge_counts_the_request_and_returns_to_zero(svc):
    client, registry = svc
    assert client.get("/inflight").json() == {"value": 1.0}
    assert registry.get_sample_value("http_requests_in_flight", {"service": "svc"}) == 0.0


def test_durations_are_observed_per_template(svc):
    client, registry = svc
    client.get("/api/v1/projects/7/cases/3")
    labels = {"service": "svc", "method": "GET", "endpoint": CASE}
    assert registry.get_sample_value("http_requests_duration_seconds_count", labels) == 1
    assert registry.get_sample_value("http_requests_duration_seconds_bucket", {**labels, "le": "30.0"}) == 1
    assert registry.get_sample_value("http_requests_duration_seconds_bucket", {**labels, "le": "0.01"}) is not None


def test_build_info_is_one_with_version_and_commit(svc):
    _, registry = svc
    assert registry.get_sample_value("build_info", {"service": "svc", "version": "1.2.3", "commit": "abc1234"}) == 1


def test_build_info_falls_back_to_the_environment_then_defaults(monkeypatch):
    monkeypatch.setenv("QEOS_VERSION", "0.4.0")
    monkeypatch.setenv("QEOS_COMMIT", "7802daf")
    _, registry = make_app(version=None, commit=None)
    assert registry.get_sample_value("build_info", {"service": "svc", "version": "0.4.0", "commit": "7802daf"}) == 1
    monkeypatch.delenv("QEOS_VERSION")
    monkeypatch.delenv("QEOS_COMMIT")
    _, registry = make_app(version=None, commit=None)
    assert registry.get_sample_value("build_info", {"service": "svc", "version": "dev", "commit": "unknown"}) == 1


def test_metrics_endpoint_serves_prometheus_text(svc):
    client, _ = svc
    client.get("/api/v1/projects/7/cases/3")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "api_requests_total" in response.text


def test_metrics_is_not_in_the_openapi_schema(svc):
    client, _ = svc
    assert "/metrics" not in client.get("/openapi.json").json()["paths"]


def test_a_given_registry_is_used_and_keeps_its_own_metrics():
    registry = CollectorRegistry()
    Counter("qav_ingest_runs", "Test runs stored", registry=registry).inc()
    app, used = make_app(registry=registry)
    assert used is registry
    with TestClient(app) as client:
        text = client.get("/metrics").text
    assert "qav_ingest_runs_total 1.0" in text and "build_info" in text


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="ProcessCollector reads /proc (Ruling 21)")
def test_process_metrics_are_exposed(svc):
    client, _ = svc
    text = client.get("/metrics").text
    for name in ("process_cpu_seconds_total", "process_resident_memory_bytes", "process_open_fds"):
        assert name in text
