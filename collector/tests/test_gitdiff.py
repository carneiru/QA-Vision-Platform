"""collect_changes shells out to git and must never break an upload: any git
failure returns None and the run goes up without change data."""

import subprocess

from qav_collector.gitdiff import collect_changes


def fake_git(responses):
    """responses: {command-tuple-suffix: stdout or Exception}."""
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        for suffix, out in responses.items():
            if tuple(cmd[-len(suffix):]) == tuple(suffix):
                if isinstance(out, Exception):
                    raise out
                return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
        raise AssertionError(f"unexpected git call: {cmd}")

    run.calls = calls
    return run


NUMSTAT = "12\t3\tsrc/app.py\0-\t-\tassets/logo.png\0"
NAME_STATUS = "M\0src/app.py\0A\0assets/logo.png\0"


def test_github_pr_diffs_against_the_base_branch():
    run = fake_git({
        ("--numstat",): None,  # placeholder, replaced below
    })
    run = fake_git({
        ("diff", "--numstat", "-z", "origin/main...HEAD"): NUMSTAT,
        ("diff", "--name-status", "-z", "origin/main...HEAD"): NAME_STATUS,
    })
    changes = collect_changes({"GITHUB_BASE_REF": "main"}, commit="abc1234", run=run)
    assert changes == {
        "base_ref": "origin/main",
        "truncated": False,
        "files": [
            {"path": "src/app.py", "status": "M", "additions": 12, "deletions": 3},
            {"path": "assets/logo.png", "status": "A", "additions": None, "deletions": None},
        ],
    }


def test_without_a_base_branch_diffs_against_the_commit_parent():
    run = fake_git({
        ("diff", "--numstat", "-z", "abc1234^..abc1234"): "1\t1\ta.py\0",
        ("diff", "--name-status", "-z", "abc1234^..abc1234"): "M\0a.py\0",
    })
    changes = collect_changes({}, commit="abc1234", run=run)
    assert changes["base_ref"] == "abc1234^"
    assert changes["files"] == [{"path": "a.py", "status": "M", "additions": 1, "deletions": 1}]


def test_renames_carry_the_new_path():
    run = fake_git({
        ("diff", "--numstat", "-z", "origin/main...HEAD"): "5\t0\t\0old.py\0new.py\0",
        ("diff", "--name-status", "-z", "origin/main...HEAD"): "R100\0old.py\0new.py\0",
    })
    changes = collect_changes({"GITHUB_BASE_REF": "main"}, commit="abc", run=run)
    assert changes["files"] == [{"path": "new.py", "status": "R", "additions": 5, "deletions": 0}]


def test_caps_the_file_list_and_flags_truncation():
    numstat = "".join(f"1\t1\tf{i}.py\0" for i in range(1200))
    name_status = "".join(f"M\0f{i}.py\0" for i in range(1200))
    run = fake_git({
        ("diff", "--numstat", "-z", "origin/main...HEAD"): numstat,
        ("diff", "--name-status", "-z", "origin/main...HEAD"): name_status,
    })
    changes = collect_changes({"GITHUB_BASE_REF": "main"}, commit="abc", run=run)
    assert changes["truncated"] is True
    assert len(changes["files"]) == 1000


def test_git_failure_returns_none():
    def run(cmd, **kwargs):
        raise FileNotFoundError("git not found")

    assert collect_changes({"GITHUB_BASE_REF": "main"}, commit="abc", run=run) is None


def test_no_commit_and_no_base_returns_none():
    assert collect_changes({}, commit=None, run=fake_git({})) is None


def test_commit_info_reads_author_and_subject():
    from qav_collector.gitdiff import collect_commit_info

    run = fake_git({("log", "-1", "--format=%an%n%s", "abc1234"): "Ada Lovelace\nfix: keep totals stable\n"})
    assert collect_commit_info("abc1234", run=run) == ("Ada Lovelace", "fix: keep totals stable")


def test_commit_info_survives_git_failure():
    from qav_collector.gitdiff import collect_commit_info

    def run(cmd, **kwargs):
        raise FileNotFoundError("no git")

    assert collect_commit_info("abc1234", run=run) == (None, None)
    assert collect_commit_info(None, run=fake_git({})) == (None, None)
