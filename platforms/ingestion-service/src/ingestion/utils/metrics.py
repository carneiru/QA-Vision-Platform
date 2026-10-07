"""Prometheus metrics, on their own registry so /metrics shows only what this service defines.
Served inside the Docker network; the gateway does not route /metrics."""
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

REGISTRY = CollectorRegistry()

# The qav_ prefix predates the QEOS rename and is kept for compatibility: renaming a metric breaks
# every dashboard and alert built on it.

RUNS = Counter("qav_ingest_runs", "Test runs stored", registry=REGISTRY)
RESULTS = Counter("qav_ingest_results", "Test results stored", registry=REGISTRY)
REJECTED = Counter("qav_ingest_rejected", "Uploads rejected", ["reason"], registry=REGISTRY)
DURATION = Histogram("qav_ingest_duration_seconds", "Time to handle POST /collect/runs", registry=REGISTRY)
REDACTIONS = Counter(
    "qav_ingest_redactions", "Results in which masking replaced a kind of secret or personal data", ["kind"],
    registry=REGISTRY,
)

# Pre-create each reason's series so it is visible (at 0) before the first rejection
for _reason in ("auth", "validation", "conflict"):
    REJECTED.labels(reason=_reason)

CONTENT_TYPE = CONTENT_TYPE_LATEST


def render() -> bytes:
    return generate_latest(REGISTRY)
