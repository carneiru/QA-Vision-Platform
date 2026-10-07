"""The names from before the QEOS rename keep working: QAV_* environment variables,
`.qav.yml` and the `qav-collector` command, each with a one-line deprecation warning.
CI pipelines already use them, so they must not break."""
from datetime import datetime, timezone
from importlib.metadata import distribution

import pytest

from qeos_collector import cli
from qeos_collector.cli import main, main_deprecated, resolve_env
from qeos_collector.config_file import load_config

KEY = "qeos_legacy_secret_key"
NOW = datetime(2026, 9, 29, 10, 5, tzinfo=timezone.utc)
RECEIPT = {"id": 42, "project_id": 1, "total": 1, "passed": 1, "failed": 0, "skipped": 0, "errored": 0,
           "created_at": "2026-09-29T10:05:00Z"}
REPORT = '<testsuite name="s"><testcase classname="c" name="passes" time="0.1"/></testsuite>'


@pytest.fixture
def report(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text(REPORT, encoding="utf-8")
    return path


def run(argv, env):
    return main(argv, env, now=lambda: NOW, sleep=lambda seconds: None)


def deprecations(err):
    return [line for line in err.splitlines() if "is deprecated" in line]


def test_resolve_env_copies_legacy_names_and_reports_them():
    resolved, legacy = resolve_env({"QAV_URL": "https://a", "QAV_GATE": "1", "OTHER": "x"})
    assert resolved["QEOS_URL"] == "https://a"
    assert resolved["QEOS_GATE"] == "1"
    assert resolved["OTHER"] == "x"
    assert sorted(legacy) == ["QAV_GATE", "QAV_URL"]


def test_resolve_env_maps_only_the_collector_variables():
    """QAV_BACKUP_DIR and the like belong to other tools: no mapping, no warning."""
    resolved, legacy = resolve_env({"QAV_BACKUP_DIR": "/b", "QAV_PATTERNS": "x", "QAV_SPOOL": "/s"})
    assert "QEOS_BACKUP_DIR" not in resolved and "QEOS_PATTERNS" not in resolved
    assert resolved["QEOS_SPOOL"] == "/s"
    assert legacy == ["QAV_SPOOL"]


def test_resolve_env_new_name_wins():
    resolved, legacy = resolve_env({"QEOS_URL": "https://new", "QAV_URL": "https://old"})
    assert resolved["QEOS_URL"] == "https://new"
    assert legacy == []


def test_legacy_env_uploads_with_one_warning_per_variable(platform, report, capsys):
    platform.reply(201, RECEIPT)
    assert run(["upload", str(report)], {"QAV_URL": platform.url, "QAV_API_KEY": KEY}) == 0
    assert len(platform.requests) == 1
    assert platform.requests[0]["headers"]["Authorization"] == f"Bearer {KEY}"
    err = capsys.readouterr().err
    assert sorted(deprecations(err)) == [
        "qeos: QAV_API_KEY is deprecated; use QEOS_API_KEY",
        "qeos: QAV_URL is deprecated; use QEOS_URL",
    ]
    assert KEY not in err


def test_new_env_wins_over_legacy_env(platform, report, capsys):
    platform.reply(201, RECEIPT)
    env = {"QEOS_URL": platform.url, "QEOS_API_KEY": KEY,
           "QAV_URL": "https://old.example", "QAV_API_KEY": "qav_old_key"}
    assert run(["upload", str(report)], env) == 0
    assert platform.requests[0]["headers"]["Authorization"] == f"Bearer {KEY}"
    assert deprecations(capsys.readouterr().err) == []


def test_legacy_flag_variables_still_apply(platform, report):
    platform.reply(422, {"detail": "rejected"})
    env = {"QAV_URL": platform.url, "QAV_API_KEY": KEY, "QAV_FAIL_ON_ERROR": "true", "QAV_NO_CHANGES": "1"}
    assert run(["upload", str(report)], env) == 1


def test_check_accepts_legacy_env(platform, capsys):
    platform.reply(200, {"project_id": 3, "name": "ci"})
    assert run(["check"], {"QAV_URL": platform.url, "QAV_API_KEY": KEY}) == 0
    assert "key: ok (project 3" in capsys.readouterr().err


def test_legacy_config_file_is_read_when_the_new_one_is_missing(tmp_path):
    (tmp_path / ".qav.yml").write_text("environment: legacy\n", encoding="utf-8")
    assert load_config(str(tmp_path)) == {"environment": "legacy"}


def test_new_config_file_wins(tmp_path):
    (tmp_path / ".qav.yml").write_text("environment: legacy\n", encoding="utf-8")
    (tmp_path / ".qeos.yml").write_text("environment: current\n", encoding="utf-8")
    assert load_config(str(tmp_path)) == {"environment": "current"}


def test_legacy_config_file_warns_once(platform, report, tmp_path, monkeypatch, capsys):
    (tmp_path / ".qav.yml").write_text(f"url: {platform.url}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    platform.reply(201, RECEIPT)
    assert run(["upload", str(report)], {"QEOS_API_KEY": KEY}) == 0
    assert deprecations(capsys.readouterr().err) == ["qeos: .qav.yml is deprecated; rename it to .qeos.yml"]


def test_deprecated_command_warns_then_runs(capsys, monkeypatch):
    monkeypatch.setattr(cli.sys, "argv", ["qav-collector", "--version"])
    assert main_deprecated() == 0
    captured = capsys.readouterr()
    assert captured.err.splitlines()[0] == "qav-collector is deprecated; use qeos-collector"
    assert "qeos-collector" in captured.out


def test_both_console_scripts_are_installed():
    scripts = {ep.name: ep.value for ep in distribution("qeos-collector").entry_points
               if ep.group == "console_scripts"}
    assert scripts == {"qeos-collector": "qeos_collector.cli:main",
                       "qav-collector": "qeos_collector.cli:main_deprecated"}
