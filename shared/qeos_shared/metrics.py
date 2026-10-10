"""Prometheus metrics for every QEOS service: one call, `install_metrics(app, service="project")`.

It adds a middleware that counts and times each request, `GET /metrics` serving the service's
registry, prometheus_client's process collector and `build_info`. Names and labels follow the
architecture blueprint §11.2 (spec docs/superpowers/specs/2026-10-10-monitoring-design.md §3):

    api_requests_total{service, endpoint, method, status_code}
    http_requests_duration_seconds{service, endpoint, method}
    http_requests_in_flight{service}
    build_info{service, version, commit}   always 1

`endpoint` is the matched route template, never the raw path, and a request matching no route is
"unmatched"; an HTTP method outside METHODS is "other". So no label ever carries a user,
organisation, project, test or case identifier, and a scanner cannot create series. /metrics and
/health are not counted.

/metrics is served inside the Docker network only: the gateway does not route it (its catch-all
serves the dashboard SPA).

A sub-app added with `app.mount("/sub", other)` is one route to the parent: every request under it
shares the single endpoint label "/sub/{path}", whatever the inner path.

Call install_metrics before adding any catch-all mount or route: /metrics is registered when it is
called, and an earlier catch-all would answer /metrics instead.

Calling it again with the same registry (a second app) is allowed and reuses the same metrics.

One uvicorn worker per service is assumed. With several workers each process keeps its own
counters and a scrape sees only one of them: switch to prometheus_client's multi-process mode
(PROMETHEUS_MULTIPROC_DIR) before adding workers.
"""
import os
import time
import weakref
from typing import Optional

from fastapi import FastAPI
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    ProcessCollector,
    generate_latest,
)
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Up to 30 s, so report calls near the 20 s statement timeout stay visible
BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0)
NOT_COUNTED = frozenset({"/metrics", "/health"})
UNMATCHED = "unmatched"
METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


class _Metrics:
    def __init__(self, registry: CollectorRegistry, service: str, version: str, commit: str) -> None:
        self.service = service
        self.requests = Counter(
            "api_requests", "HTTP requests handled", ["service", "endpoint", "method", "status_code"],
            registry=registry,
        )
        self.duration = Histogram(
            "http_requests_duration_seconds", "Time to handle an HTTP request", ["service", "endpoint", "method"],
            buckets=BUCKETS, registry=registry,
        )
        self.in_flight = Gauge("http_requests_in_flight", "HTTP requests being handled", ["service"], registry=registry)
        build_info = Gauge("build_info", "Always 1; the labels say what is deployed", ["service", "version", "commit"],
                           registry=registry)
        build_info.labels(service, version, commit).set(1)
        self.in_flight.labels(service)  # visible at 0 before the first request


# Metric set per registry, so installing twice on one registry reuses it instead of raising
_INSTALLED: "weakref.WeakKeyDictionary[CollectorRegistry, _Metrics]" = weakref.WeakKeyDictionary()


def _template(route) -> str:
    return getattr(route, "path_format", None) or getattr(route, "path", None) or UNMATCHED


def route_template(app: FastAPI, scope: Scope) -> str:
    """The template of the route that will handle this request; a known path with the wrong method
    (405) keeps its template, anything else is "unmatched"."""
    partial = None
    for route in app.router.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return _template(route)
        if match == Match.PARTIAL and partial is None:
            partial = route
    return _template(partial) if partial is not None else UNMATCHED


class MetricsMiddleware:
    """Pure ASGI (no BaseHTTPMiddleware), so streaming responses and background tasks are untouched."""

    def __init__(self, app: ASGIApp, metrics: _Metrics, fastapi_app: FastAPI) -> None:
        self.app = app
        self.metrics = metrics
        self.fastapi_app = fastapi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in NOT_COUNTED:
            await self.app(scope, receive, send)
            return
        service = self.metrics.service
        endpoint = route_template(self.fastapi_app, scope)
        method = scope["method"] if scope["method"] in METHODS else "other"
        status_code = 500  # an exception before the response starts becomes ServerErrorMiddleware's 500

        async def send_and_record_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        in_flight = self.metrics.in_flight.labels(service)
        in_flight.inc()
        started = time.perf_counter()
        try:
            await self.app(scope, receive, send_and_record_status)
        finally:
            in_flight.dec()
            self.metrics.duration.labels(service, endpoint, method).observe(time.perf_counter() - started)
            self.metrics.requests.labels(service, endpoint, method, str(status_code)).inc()


def install_metrics(
    app: FastAPI,
    service: str,
    registry: Optional[CollectorRegistry] = None,
    *,
    version: Optional[str] = None,
    commit: Optional[str] = None,
) -> CollectorRegistry:
    """Instrument `app` and serve `GET /metrics` from `registry` (a new one when None; ingestion passes
    its own so its qav_* metrics stay on the same page). Call once per app, at import time."""
    registry = registry if registry is not None else CollectorRegistry()
    metrics = _INSTALLED.get(registry)
    if metrics is None:
        ProcessCollector(registry=registry)
        metrics = _Metrics(
            registry,
            service,
            version or os.environ.get("QEOS_VERSION") or "dev",
            commit or os.environ.get("QEOS_COMMIT") or "unknown",
        )
        _INSTALLED[registry] = metrics
    app.add_middleware(MetricsMiddleware, metrics=metrics, fastapi_app=app)

    def metrics_endpoint() -> Response:
        return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)
    return registry
