"""POST /analytics/duration-estimate: how long a Play of these tests should take, from the last 30 days."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.ingestion.api.deps import READ_ROLES
from src.ingestion.api.v1.endpoints import analytics
from src.ingestion.service.ingest_service import test_key as key_of

URL = "/api/v1/projects/1/analytics/duration-estimate"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
T1, UNKNOWN = key_of("s", "C", "t1"), "f" * 64  # seed_run names its results in suite "s", class "C"


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    monkeypatch.setattr(analytics, "_now", lambda: NOW)


@pytest.fixture
def viewer(project_role):
    project_role("viewer", project_id=1)


def ago(hours):
    return NOW - timedelta(hours=hours)


def one_test_runs(seed_run, durations, name="t1", status="passed", environment=None):
    """One run per duration, the run's wall time equal to its one test: the fallback factor is then 1."""
    for i, duration in enumerate(durations):
        seed_run(ago(i + 1), results=((name, status, duration),), duration_ms=duration, environment=environment)


def estimate(client, auth, keys=(T1,), **body):
    r = client.post(URL, json={"test_keys": list(keys), **body}, headers=auth())
    assert r.status_code == 200, r.text
    return r.json()


def test_typical_is_the_median_of_passes_and_upper_the_p90_with_failures(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 200, 300])
    seed_run(ago(10), results=(("t1", "failed", 5000),), duration_ms=5000)
    seed_run(ago(11), results=(("t1", "skipped", 0), ("t2", "passed", 50)), duration_ms=50)
    data = estimate(client, auth)
    assert data["model"] == {"overhead_ms": 0, "factor": 1.0, "runs": 5, "fitted": True}  # wall = serial
    assert data["estimate_ms"] == 200
    assert data["upper_ms"] == 3590  # p90 of 100, 200, 300, 5000: 300 + 0.7 * 4700
    assert (data["tests_with_history"], data["tests_without_history"]) == (1, 0)


def test_the_fallback_model_with_a_wall_equal_to_serial_is_factor_one(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 200, 300, 400])
    data = estimate(client, auth)
    assert data["model"] == {"overhead_ms": 0, "factor": 1.0, "runs": 4, "fitted": False}
    assert (data["estimate_ms"], data["upper_ms"]) == (250, 370)


def test_a_test_that_never_passed_takes_the_median_of_its_runs(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 300], status="failed")
    seed_run(ago(5), results=(("t1", "errored", 500),), duration_ms=500)
    assert estimate(client, auth)["estimate_ms"] == 300


def test_executions_older_than_30_days_are_ignored(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 100])
    seed_run(NOW - timedelta(days=31), results=(("t1", "passed", 100_000),), duration_ms=100_000)
    assert estimate(client, auth)["estimate_ms"] == 100


def test_the_environment_is_used_from_three_executions_there(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 100, 100], environment="staging")
    one_test_runs(seed_run, [900] * 5, environment="prod")
    data = estimate(client, auth, environment="staging")
    assert (data["estimate_ms"], data["environment_used"]) == (100, 1)
    assert estimate(client, auth)["environment_used"] == 0


def test_below_three_executions_in_the_environment_every_environment_counts(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 100], environment="staging")
    one_test_runs(seed_run, [900] * 5, environment="prod")
    data = estimate(client, auth, environment="staging")
    assert (data["estimate_ms"], data["environment_used"]) == (900, 0)


def test_an_empty_environment_means_none(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 100, 100], environment="staging")
    assert estimate(client, auth, environment="")["environment_used"] == 0


def test_five_runs_fit_overhead_and_factor(client, auth, viewer, seed_run):
    for i, serial in enumerate((10_000, 20_000, 30_000, 40_000, 50_000, 60_000)):
        seed_run(ago(i + 1), results=(("t1", "passed", serial),), duration_ms=60_000 + serial // 2)
    data = estimate(client, auth)
    assert data["model"] == {"overhead_ms": 60_000, "factor": pytest.approx(0.5), "runs": 6, "fitted": True}
    assert data["estimate_ms"] == 60_000 + 35_000 // 2  # the median of the six is 35 s


def test_the_model_reads_the_last_20_runs_of_every_branch(client, auth, viewer, seed_run):
    for i in range(25):
        seed_run(ago(i + 1), results=(("t1", "passed", 1000),), duration_ms=1000, branch=f"b{i % 3}")
    assert estimate(client, auth)["model"]["runs"] == 20


def test_runs_without_results_or_with_only_skips_are_not_model_points(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 100])
    seed_run(ago(20), results=(), duration_ms=5000)
    seed_run(ago(21), results=(("t2", "skipped", 0),), duration_ms=5000)
    assert estimate(client, auth)["model"]["runs"] == 2


def test_the_fit_is_clamped(client, auth, viewer, seed_run):
    # wall = 3 x serial: more than one worker's time cannot be wall time, factor stays 1
    for i, serial in enumerate((1000, 2000, 3000, 4000, 5000)):
        seed_run(ago(i + 1), results=(("t1", "passed", serial),), duration_ms=3 * serial)
    model = estimate(client, auth)["model"]
    assert (model["fitted"], model["factor"]) == (True, 1.0)


def test_no_history_at_all_has_no_estimate(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100])
    data = estimate(client, auth, keys=(UNKNOWN,))
    assert (data["estimate_ms"], data["upper_ms"]) == (None, None)
    assert (data["tests_with_history"], data["tests_without_history"]) == (0, 1)


def test_tests_without_history_are_counted_apart(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 100])
    data = estimate(client, auth, keys=(T1, UNKNOWN))
    assert (data["estimate_ms"], data["tests_with_history"], data["tests_without_history"]) == (100, 1, 1)


def test_keys_are_lowercased_and_deduplicated(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 100])
    data = estimate(client, auth, keys=(T1, T1.upper()))
    assert (data["estimate_ms"], data["tests_with_history"], data["tests_without_history"]) == (100, 1, 0)


def test_another_projects_runs_are_invisible(client, auth, viewer, seed_run):
    one_test_runs(seed_run, [100, 100])
    seed_run(ago(1), results=(("t1", "passed", 99_000),), duration_ms=99_000, project_id=2)
    data = estimate(client, auth)
    assert (data["estimate_ms"], data["model"]["runs"]) == (100, 2)


@pytest.mark.parametrize("body", [
    {"test_keys": []}, {"test_keys": [T1] * 201}, {"test_keys": ["x"]}, {"test_keys": ["g" * 64]},
    {"test_keys": [T1], "environment": "a\x00"}, {"test_keys": [T1], "environment": "e" * 101},
    {"test_keys": [T1], "branch": "main"}, {},
])
def test_bad_bodies_are_422(client, auth, viewer, body):
    assert client.post(URL, json=body, headers=auth()).status_code == 422


def test_200_keys_are_accepted(client, auth, viewer):
    keys = [f"{i:064x}" for i in range(200)]
    assert estimate(client, auth, keys=keys)["tests_without_history"] == 200


@pytest.mark.parametrize("role", READ_ROLES)
def test_every_reading_role_can_ask(client, auth, project_role, role):
    project_role(role, project_id=1)
    assert client.post(URL, json={"test_keys": [T1]}, headers=auth()).status_code == 200


def test_access_failures(client, auth, project_role):
    project_role(status_code=404, body={"detail": "Project not found"}, project_id=1)
    assert client.post(URL, json={"test_keys": [T1]}, headers=auth()).status_code == 404
    project_role(exc=httpx.ConnectError("refused"), project_id=1)
    assert client.post(URL, json={"test_keys": [T1]}, headers=auth()).status_code == 503
    assert client.post(URL, json={"test_keys": [T1]}).status_code == 401
