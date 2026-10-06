"""qav-collector import-features (ADR-024)."""
import json

import pytest

from qav_collector.cli import main

KEY = "qav_test_key_123"
GRANT = {"token": "t0k", "expires_in": 300, "project_id": 7}
SUMMARY = {"created": 1, "updated": 0, "moved": 0, "reactivated": 0, "archived": 0, "unchanged": 0,
           "skipped": 0, "mass_archive": False}
RESULT = {"plan_hash": "a" * 64, "summary": SUMMARY,
          "items": [{"action": "create", "path": "features/a.feature", "scenario": "S", "case_number": 1}],
          "errors": [], "warnings": []}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "features" / "sub").mkdir(parents=True)
    (tmp_path / "features" / "a.feature").write_text("Feature: A\n  Scenario: S\n    Given x\n", encoding="utf-8")
    (tmp_path / "features" / "sub" / "b.feature").write_text("Feature: B\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def env(platform, **extra):
    return {"QAV_URL": platform.url, "QAV_API_KEY": KEY, **extra}


def sent(platform, i):
    return json.loads(platform.requests[i]["body"])


def test_it_trades_the_key_then_runs_a_full_import(platform, repo):
    platform.reply(200, GRANT)
    platform.reply(200, RESULT)
    assert main(["import-features"], env(platform)) == 0
    token, imp = platform.requests
    assert token["path"] == "/api/v1/collect/token"
    assert token["headers"]["Authorization"] == f"Bearer {KEY}"
    assert imp["path"] == "/api/v1/projects/7/cases/import?dry_run=false"
    assert imp["headers"]["Authorization"] == "Bearer t0k"
    body = sent(platform, 1)
    assert [f["path"] for f in body["files"]] == ["features/a.feature", "features/sub/b.feature"]
    assert body["full"] is True and "allow_mass_archive" not in body


def test_flags_reach_the_request(platform, repo):
    platform.reply(200, GRANT)
    platform.reply(200, RESULT)
    assert main(["import-features", "features/*.feature", "--no-full", "--allow-mass-archive"], env(platform)) == 0
    body = sent(platform, 1)
    assert [f["path"] for f in body["files"]] == ["features/a.feature"]
    assert body["full"] is False and body["allow_mass_archive"] is True


def test_qav_yml_features_are_the_default_patterns(platform, repo):
    (repo / ".qav.yml").write_text("features:\n  - features/sub/*.feature\n", encoding="utf-8")
    platform.reply(200, GRANT)
    platform.reply(200, RESULT)
    assert main(["import-features"], env(platform)) == 0
    assert [f["path"] for f in sent(platform, 1)["files"]] == ["features/sub/b.feature"]


def test_a_pull_request_build_skips(platform, repo, capsys):
    ci = {"GITHUB_ACTIONS": "true", "GITHUB_REF_NAME": "12/merge", "GITHUB_HEAD_REF": "feature-x"}
    assert main(["import-features"], env(platform, **ci)) == 0
    assert platform.requests == []
    assert "skipped: on feature-x; cases sync from master" in capsys.readouterr().err


def test_the_sync_branch_can_be_named(platform, repo):
    platform.reply(200, GRANT)
    platform.reply(200, RESULT)
    ci = {"GITHUB_ACTIONS": "true", "GITHUB_REF_NAME": "main"}
    assert main(["import-features", "--branch", "main"], env(platform, **ci)) == 0
    assert len(platform.requests) == 2


def test_dry_run_asks_for_a_plan_and_prints_it(platform, repo, capsys):
    platform.reply(200, GRANT)
    platform.reply(200, RESULT)
    assert main(["import-features", "--dry-run"], env(platform)) == 0
    assert platform.requests[1]["path"].endswith("dry_run=true")
    err = capsys.readouterr().err
    assert "would import: 1 created" in err and "features/a.feature" in err


def test_a_refused_mass_archive_fails_the_build(platform, repo, capsys):
    platform.reply(200, GRANT)
    platform.reply(409, {"detail": {"code": "mass_archive", "message": "This would archive 9 of 10 imported cases.",
                                    "archived": 9, "live": 10}})
    assert main(["import-features"], env(platform)) == 1
    assert "This would archive 9 of 10" in capsys.readouterr().err


def test_a_bad_key_fails_the_build(platform, repo):
    platform.reply(401, {"detail": "Invalid API key"})
    assert main(["import-features"], env(platform)) == 1


def test_parse_errors_fail_only_with_strict(platform, repo):
    broken = {**RESULT, "errors": [{"path": "features/sub/b.feature", "line": 2, "message": "(2:1): expected"}]}
    for argv, code in ((["import-features"], 0), (["import-features", "--strict"], 1)):
        platform.reply(200, GRANT)
        platform.reply(200, broken)
        assert main(argv, env(platform)) == code


@pytest.mark.parametrize("environment", [{"QAV_API_KEY": KEY}, {"QAV_URL": "https://qav.example"}])
def test_missing_url_or_key_is_a_configuration_error(repo, environment):
    assert main(["import-features"], environment) == 2


def test_no_matching_files_is_a_configuration_error(platform, repo):
    assert main(["import-features", "nothing/**/*.feature"], env(platform)) == 2


def test_an_unreadable_file_is_a_configuration_error(platform, repo, capsys):
    (repo / "features" / "latin.feature").write_bytes(b"Feature: caf\xe9\n")
    assert main(["import-features"], env(platform)) == 2
    assert "latin.feature" in capsys.readouterr().err
