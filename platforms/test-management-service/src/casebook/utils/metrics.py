"""test-management's own metrics, on the registry install_metrics serves at /metrics (blueprint 11.2)."""
from prometheus_client import CollectorRegistry, Counter

REGISTRY = CollectorRegistry()

# type="manual": a person created the case (POST /cases); type="api": an applied Gherkin import or CI
# sync created it. "generated" waits for the AI engine.
CASES_CREATED = Counter("test_case_creation", "Test cases created", ["type"], registry=REGISTRY)
for _type in ("manual", "api"):
    CASES_CREATED.labels(type=_type)
