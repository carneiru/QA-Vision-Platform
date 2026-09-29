import json
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from qav_collector import __version__, cli, payload
from qav_collector.cli import main

KEY = "qav_cli_secret_key"
NOW = datetime(2026, 9, 29, 10, 5, tzinfo=timezone.utc)
RECEIPT = {"id": 42, "project_id": 1, "total": 2, "passed": 1, "failed": 1, "skipped": 0, "errored": 0,
           "created_at": "2026-09-29T10:05:00Z"}
REPORT = (
    '<testsuites><testsuite name="s" timestamp="2026-09-29T10:00:00Z">'
    '<testcase classname="c" name="passes" time="0.1"/>'
    '<testcase classname="c" name="fails" time="0.2"><failure message="boom">boom</failure></testcase>'
    '</testsuite></testsuites>'
)
GITHUB = {
    "GITHUB_ACTIONS": "true", "GITHUB_SHA": "a" * 40, "GITHUB_REF_NAME": "main",
    "GITHUB_SERVER_URL": "https://github.com", "GITHUB_REPOSITORY": "acme/shop",
    "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_JOB": "test",
}
CONFIGURED = {"QAV_URL": "https://qav.acme.test", "QAV_API_KEY": KEY}


@pytest.fixture
def report(tmp_path):
    path = tmp_path / "reports" / "junit.xml"
    path.parent.mkdir()
    path.write_text(REPORT, encoding="utf-8")
    return path


def env_for(platform, **extra):
    return {"QAV_URL": platform.url, "QAV_API_KEY": KEY, **extra}


def run(argv, env):
    return main(argv, env, now=lambda: NOW, sleep=lambda seconds: None)


def sent(platform, index=0):
    return json.loads(platform.requests[index]["body"])


def test_uploads_one_run(platform, report, capsys):
    platform.reply(201, RECEIPT)

    assert run(["upload", str(report)], env_for(platform)) == 0
    body = sent(platform)
    assert body["run"]["ci_provider"] == "local"
    assert body["run"]["started_at"] == "2026-09-29T10:00:00+00:00"
    assert body["run"]["finished_at"] == "2026-09-29T10:05:00+00:00"
    assert [r["name"] for r in body["results"]] == ["passes", "fails"]
    assert platform.requests[0]["headers"]["Idempotency-Key"].startswith("local-")
    err = capsys.readouterr().err
    assert "qav: parsed 1 file(s), 2 results (1 failed, 0 errored, 0 skipped)" in err
    assert "qav: uploaded run 42 (201)" in err


def test_each_local_invocation_gets_a_new_key(platform, report):
    platform.reply(201, RECEIPT)
    platform.reply(201, RECEIPT)
    run(["upload", str(report)], env_for(platform))
    run(["upload", str(report)], env_for(platform))

    keys = [r["headers"]["Idempotency-Key"] for r in platform.requests]
    assert keys[0] != keys[1]


def test_glob_patterns_merge_files_and_skip_duplicates(platform, report, capsys):
    nested = report.parent / "sub" / "more.xml"
    nested.parent.mkdir()
    nested.write_text(REPORT, encoding="utf-8")
    platform.reply(201, RECEIPT)

    assert run(["upload", str(report.parent / "**" / "*.xml"), str(report)], env_for(platform)) == 0
    assert len(platform.requests) == 1
    assert len(sent(platform)["results"]) == 4
    assert "parsed 2 file(s), 4 results" in capsys.readouterr().err


def test_github_actions_metadata_and_key(platform, report):
    platform.reply(201, RECEIPT)

    assert run(["upload", str(report)], env_for(platform, **GITHUB)) == 0
    body = sent(platform)
    assert body["run"]["ci_provider"] == "github_actions"
    assert body["run"]["commit_sha"] == "a" * 40
    assert body["run"]["branch"] == "main"
    assert body["run"]["ci_run_url"] == "https://github.com/acme/shop/actions/runs/123"
    assert platform.requests[0]["headers"]["Idempotency-Key"] == "gh-123-2-test"


def test_flags_beat_variables(platform, report):
    platform.reply(201, RECEIPT)
    env = env_for(platform, **GITHUB, QAV_BRANCH="from-env", QAV_IDEMPOTENCY_KEY="from env")

    argv = ["upload", str(report), "--branch", "from-flag", "--ci-provider", "other",
            "--idempotency-key", "from flag", "--environment", "staging"]
    assert run(argv, env) == 0
    body = sent(platform)
    assert body["run"]["branch"] == "from-flag"
    assert body["run"]["ci_provider"] == "other"
    assert body["run"]["environment"] == "staging"
    assert platform.requests[0]["headers"]["Idempotency-Key"] == "from-flag"


def test_variables_beat_detection(platform, report):
    platform.reply(201, RECEIPT)
    env = env_for(platform, **GITHUB, QAV_BRANCH="from-env", QAV_COMMIT="b" * 40,
                  QAV_IDEMPOTENCY_KEY="from env", QAV_CI_PROVIDER="other")

    assert run(["upload", str(report)], env) == 0
    body = sent(platform)
    assert body["run"]["branch"] == "from-env"
    assert body["run"]["commit_sha"] == "b" * 40
    assert body["run"]["ci_provider"] == "other"
    assert platform.requests[0]["headers"]["Idempotency-Key"] == "from-env"


def test_dry_run_prints_the_json_and_needs_no_key(report, capsys):
    assert run(["upload", str(report), "--dry-run"], {}) == 0

    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert [r["name"] for r in body["results"]] == ["passes", "fails"]
    assert body["run"]["ci_provider"] == "local"
    assert "qav: dry run: 1 part(s), nothing uploaded" in captured.err


def test_parts_are_uploaded_in_order_and_a_failure_names_what_was_stored(platform, report, monkeypatch, capsys):
    monkeypatch.setattr(payload, "MAX_RESULTS_PER_PART", 1)
    platform.reply(201, RECEIPT)
    platform.reply(401, {"detail": "Invalid API key"})

    assert run(["upload", str(report), "--idempotency-key", "job-7"], env_for(platform)) == 0
    assert [r["headers"]["Idempotency-Key"] for r in platform.requests] == ["job-7-part-1", "job-7-part-2"]
    err = capsys.readouterr().err
    assert "qav: uploaded run 42 (201), part 1 of 2" in err
    assert "qav: upload failed: the API key is invalid or revoked (401)" in err
    assert "qav: stored before the failure: run 42 (part 1 of 2)" in err
    assert "qav: not failing the build (pass --fail-on-error to change that)" in err


def test_an_upload_failure_exits_0_by_default(platform, report):
    platform.reply(401, {"detail": "Invalid API key"})
    assert run(["upload", str(report)], env_for(platform)) == 0


@pytest.mark.parametrize("argv_extra, env_extra", [
    (["--fail-on-error"], {}),
    ([], {"QAV_FAIL_ON_ERROR": "1"}),
    ([], {"QAV_FAIL_ON_ERROR": "true"}),
])
def test_fail_on_error_exits_1(platform, report, argv_extra, env_extra):
    platform.reply(401, {"detail": "Invalid API key"})
    assert run(["upload", str(report), *argv_extra], env_for(platform, **env_extra)) == 1


@pytest.mark.parametrize("argv_extra, env, message", [
    ([], {"QAV_API_KEY": KEY}, "QAV_URL is not set"),
    ([], {"QAV_URL": "https://qav.acme.test"}, "QAV_API_KEY is not set"),
    ([], {"QAV_URL": "http://qav.acme.test", "QAV_API_KEY": KEY}, "must be an https:// URL"),
    (["--ca-file", "missing.pem"], CONFIGURED, "cannot use --ca-file"),
    ([], {**CONFIGURED, "QAV_CA_FILE": "missing.pem"}, "cannot use --ca-file"),
    ([], {**CONFIGURED, "QAV_CI_PROVIDER": "travis"}, "QAV_CI_PROVIDER must be one of"),
    (["--fail-on-error"], {"QAV_API_KEY": KEY}, "QAV_URL is not set"),
])
def test_configuration_errors_exit_2(report, capsys, argv_extra, env, message):
    assert run(["upload", str(report), *argv_extra], env) == 2
    assert message in capsys.readouterr().err


def test_no_file_matched_exits_2(tmp_path, capsys):
    assert run(["upload", str(tmp_path / "*.xml")], CONFIGURED) == 2
    assert "no file matched" in capsys.readouterr().err


def test_files_without_test_cases_upload_nothing(platform, tmp_path, capsys):
    empty = tmp_path / "empty.xml"
    empty.write_text("<testsuites/>", encoding="utf-8")

    assert run(["upload", str(empty)], env_for(platform)) == 0
    assert platform.requests == []
    assert "qav: no test results found" in capsys.readouterr().err


def test_skipped_files_are_reported_and_the_rest_uploaded(platform, report, capsys):
    broken = report.parent / "broken.xml"
    broken.write_text("<testsuite>", encoding="utf-8")
    platform.reply(201, RECEIPT)

    assert run(["upload", str(report.parent / "*.xml")], env_for(platform)) == 0
    assert len(sent(platform)["results"]) == 2
    err = capsys.readouterr().err
    assert f"qav: skipped {broken}: not well-formed XML" in err
    assert "parsed 1 file(s)" in err


def test_usage_errors_exit_2(capsys):
    assert run([], {}) == 2
    assert run(["upload"], {}) == 2
    assert run(["upload", "x.xml", "--ci-provider", "travis"], {}) == 2


def test_version(capsys):
    assert run(["--version"], {}) == 0
    assert capsys.readouterr().out.strip() == f"qav-collector {__version__}"


def test_python_dash_m_runs_the_cli():
    completed = subprocess.run([sys.executable, "-m", "qav_collector", "--version"], capture_output=True, text=True)
    assert completed.returncode == 0
    assert completed.stdout.strip() == f"qav-collector {__version__}"


def test_the_key_never_appears_in_the_output(platform, report, capsys):
    platform.reply(422, {"detail": f"bad token {KEY}"})

    run(["upload", str(report)], env_for(platform))
    err = capsys.readouterr().err
    assert KEY not in err
    assert "bad token ***" in err


@pytest.mark.parametrize("argv_extra, code", [([], 0), (["--fail-on-error"], 1)])
def test_an_unexpected_error_follows_the_upload_failure_rule(platform, report, monkeypatch, capsys, argv_extra, code):
    def explode(*args, **kwargs):
        raise RuntimeError(f"boom {KEY}")

    monkeypatch.setattr(cli, "upload_part", explode)

    assert run(["upload", str(report), *argv_extra], env_for(platform)) == code
    err = capsys.readouterr().err
    assert "qav: unexpected error: RuntimeError: boom ***" in err
    assert KEY not in err
