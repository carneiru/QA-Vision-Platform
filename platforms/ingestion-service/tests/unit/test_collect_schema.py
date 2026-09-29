from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.ingestion.schemas.collect import RunUpload

NOW = datetime.now(timezone.utc)


def body(run=None, results=None):
    r = {"ci_provider": "github_actions", "started_at": (NOW - timedelta(minutes=5)).isoformat(),
         "finished_at": NOW.isoformat()}
    r.update(run or {})
    return {"run": r, "results": results if results is not None else [{"name": "t", "status": "passed"}]}


def test_minimal_upload_is_valid_with_defaults():
    upload = RunUpload.model_validate(body())
    result = upload.results[0]
    assert (result.suite, result.class_name, result.duration_ms) == ("", "", 0)


def test_error_status_becomes_errored():
    upload = RunUpload.model_validate(body(results=[{"name": "t", "status": "error"}]))
    assert upload.results[0].status == "errored"


@pytest.mark.parametrize(
    "run",
    [
        {"ci_provider": "travis"},
        {"started_at": "2026-09-29T10:00:00"},                              # no timezone
        {"started_at": NOW.isoformat(), "finished_at": (NOW - timedelta(seconds=1)).isoformat()},
        {"finished_at": (NOW + timedelta(days=1)).isoformat()},
        {"commit_sha": "xyz1234"},
        {"commit_sha": "abc12"},
        {"ci_run_url": "javascript:alert(1)"},
        {"branch": "b" * 256},
        {"unexpected": "field"},
    ],
)
def test_invalid_run_fields(run):
    with pytest.raises(ValidationError):
        RunUpload.model_validate(body(run=run))


def test_finished_at_slightly_in_the_future_is_accepted():
    RunUpload.model_validate(body(run={"finished_at": (NOW + timedelta(minutes=10)).isoformat()}))


@pytest.mark.parametrize(
    "result",
    [
        {"status": "passed"},                        # no name
        {"name": "   ", "status": "passed"},
        {"name": "t", "status": "flaky"},
        {"name": "t", "status": "passed", "duration_ms": -1},
        {"name": "t", "status": "passed", "extra": 1},
        {"name": "n" * 1001, "status": "passed"},
    ],
)
def test_invalid_results(result):
    with pytest.raises(ValidationError):
        RunUpload.model_validate(body(results=[result]))


def test_empty_results_are_rejected():
    with pytest.raises(ValidationError):
        RunUpload.model_validate(body(results=[]))


def test_too_many_results_are_rejected():
    from src.ingestion.core.config import settings

    too_many = [{"name": f"t{i}", "status": "passed"} for i in range(settings.MAX_RESULTS_PER_RUN + 1)]
    with pytest.raises(ValidationError):
        RunUpload.model_validate(body(results=too_many))


def test_long_text_is_accepted_by_the_schema():
    # truncation is the service's job; the schema must not reject long text
    RunUpload.model_validate(body(results=[{"name": "t", "status": "failed", "details": "x" * 200_000}]))
