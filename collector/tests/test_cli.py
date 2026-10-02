import json
import re
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
    assert re.fullmatch(r"gh-123-2-test-[0-9a-f]{12}", platform.requests[0]["headers"]["Idempotency-Key"])


def test_matrix_legs_and_repeated_uploads_in_one_job_get_different_keys(platform, report):
    # Every leg of a GitHub matrix (and every upload step in one job) sees the same run id, attempt
    # and job id; the server answers 409 when one key comes with a different body, so a shared key
    # would lose every upload after the first
    platform.reply(201, RECEIPT)
    platform.reply(201, dict(RECEIPT, id=43))

    assert run(["upload", str(report)], env_for(platform, **GITHUB)) == 0
    assert run(["upload", str(report)], env_for(platform, **GITHUB)) == 0
    first, second = (r["headers"]["Idempotency-Key"] for r in platform.requests)
    assert first != second
    assert first.startswith("gh-123-2-test-") and second.startswith("gh-123-2-test-")


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


@pytest.mark.parametrize("bad_key", ["qav_first\nsecond", "qav_has xyzzy", "qav_café"])
def test_an_unusable_api_key_is_a_configuration_error_and_is_never_printed(report, capsys, bad_key):
    assert run(["upload", str(report)], {"QAV_URL": "https://qav.acme.test", "QAV_API_KEY": bad_key}) == 2
    err = capsys.readouterr().err
    assert "QAV_API_KEY" in err
    for piece in bad_key.split():
        assert piece not in err


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


SHA_A = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"


def test_component_flags_are_sent(platform, report):
    platform.reply(201, RECEIPT)

    argv = ["upload", str(report), "--component", f"product-api@{SHA_A}", "--component", "web@0f1e2d3c"]
    assert run(argv, env_for(platform)) == 0
    assert sent(platform)["components"] == [
        {"name": "product-api", "sha": SHA_A},
        {"name": "web", "sha": "0f1e2d3c"},
    ]


def test_components_from_environment(platform, report):
    platform.reply(201, RECEIPT)

    env = env_for(platform, QAV_COMPONENTS=f"product-api@{SHA_A},web@0f1e2d3c")
    assert run(["upload", str(report)], env) == 0
    assert sent(platform)["components"] == [
        {"name": "product-api", "sha": SHA_A},
        {"name": "web", "sha": "0f1e2d3c"},
    ]


def test_component_flags_beat_the_environment(platform, report):
    platform.reply(201, RECEIPT)

    env = env_for(platform, QAV_COMPONENTS="ignored@0f1e2d3c")
    assert run(["upload", str(report), "--component", "web@aa11bb22"], env) == 0
    assert sent(platform)["components"] == [{"name": "web", "sha": "aa11bb22"}]


def test_no_components_means_no_components_key(platform, report):
    platform.reply(201, RECEIPT)

    assert run(["upload", str(report)], env_for(platform)) == 0
    assert "components" not in sent(platform)


@pytest.mark.parametrize("value, complaint", [
    ("missing-separator", "NAME@SHA"),
    ("api@not-hex!", "hexadecimal"),
    ("@0f1e2d3c", "NAME@SHA"),
    ("api@0f1e2d3c,api@aa11bb22", "unique"),
])
def test_bad_components_are_a_config_error(platform, report, capsys, value, complaint):
    env = env_for(platform, QAV_COMPONENTS=value)
    assert run(["upload", str(report)], env) == 2
    assert complaint in capsys.readouterr().err


def test_check_passes_and_uploads_nothing(platform, report, capsys):
    platform.reply(200, {"project_id": 7, "name": "ci"})

    assert run(["check", str(report)], env_for(platform)) == 0
    err = capsys.readouterr().err
    assert "qav: url: ok" in err
    assert "qav: key: ok (project 7, key 'ci')" in err
    assert "qav: reports: 1 file(s), 2 results" in err
    assert [r["path"] for r in platform.requests] == ["/api/v1/collect/key"]


def test_check_without_patterns_checks_config_only(platform, capsys):
    platform.reply(200, {"project_id": 7, "name": "ci"})

    assert run(["check"], env_for(platform)) == 0
    assert "reports:" not in capsys.readouterr().err


def test_check_reports_a_bad_key(platform, capsys):
    platform.reply(401, {"detail": "Invalid API key"})

    assert run(["check"], env_for(platform)) == 2
    assert "invalid or revoked" in capsys.readouterr().err


def test_check_fails_when_no_file_matches(platform, capsys):
    platform.reply(200, {"project_id": 7, "name": "ci"})

    assert run(["check", "no-such-*.xml"], env_for(platform)) == 2
    assert "no file matched" in capsys.readouterr().err


def test_check_needs_a_url(capsys):
    assert run(["check"], {"QAV_API_KEY": KEY}) == 2
    assert "QAV_URL" in capsys.readouterr().err


def test_check_needs_a_key(platform, capsys):
    assert run(["check"], {"QAV_URL": platform.url}) == 2
    assert "QAV_API_KEY" in capsys.readouterr().err


def test_a_failed_upload_is_spooled_for_the_next_run(platform, report, tmp_path, capsys):
    for _ in range(5):
        platform.reply(503, {"detail": "down"})

    assert run(["upload", str(report), "--spool", str(tmp_path), "--idempotency-key", "job-9"],
               env_for(platform)) == 0
    err = capsys.readouterr().err
    assert "qav: spooled 1 part(s) for the next run" in err
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1


def test_spooled_parts_are_resent_before_the_current_run(platform, report, tmp_path, capsys):
    for _ in range(5):
        platform.reply(503, {"detail": "down"})
    assert run(["upload", str(report), "--spool", str(tmp_path), "--idempotency-key", "job-9"],
               env_for(platform)) == 0

    platform.reply(201, RECEIPT)  # the spooled part
    platform.reply(201, RECEIPT)  # the current run
    assert run(["upload", str(report), "--spool", str(tmp_path), "--idempotency-key", "job-10"],
               env_for(platform)) == 0
    keys = [r["headers"]["Idempotency-Key"] for r in platform.requests[5:]]
    assert keys == ["job-9", "job-10"]
    assert list(tmp_path.glob("*.json")) == []
    assert "qav: resent 1 spooled part(s)" in capsys.readouterr().err


def test_a_still_failing_spooled_part_is_kept_and_the_run_continues(platform, report, tmp_path, capsys):
    for _ in range(5):
        platform.reply(503, {"detail": "down"})
    assert run(["upload", str(report), "--spool", str(tmp_path), "--idempotency-key", "job-9"],
               env_for(platform)) == 0

    for _ in range(5):
        platform.reply(503, {"detail": "still down"})  # the spooled part
    platform.reply(201, RECEIPT)  # the current run succeeds
    assert run(["upload", str(report), "--spool", str(tmp_path), "--idempotency-key", "job-10"],
               env_for(platform)) == 0
    assert len(list(tmp_path.glob("*.json"))) == 1
    err = capsys.readouterr().err
    assert "qav: a spooled part still fails" in err
    assert "qav: uploaded run 42 (201)" in err


def test_a_rejected_upload_is_not_spooled(platform, report, tmp_path):
    platform.reply(401, {"detail": "Invalid API key"})

    assert run(["upload", str(report), "--spool", str(tmp_path)], env_for(platform)) == 0
    assert list(tmp_path.glob("*.json")) == []


def test_no_spool_flag_means_no_spooling(platform, report, tmp_path):
    for _ in range(5):
        platform.reply(503, {"detail": "down"})
    assert run(["upload", str(report)], env_for(platform)) == 0
    assert list(tmp_path.glob("*.json")) == []
