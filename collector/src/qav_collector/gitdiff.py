"""Code-change data for a run: changed files and diff stats against the base.

Everything here is best effort. A missing git, a shallow clone, an unknown
base — any failure returns None and the upload proceeds without change data;
a diff must never break the build.
"""

import subprocess
from typing import Callable, Mapping, Optional

MAX_FILES = 1000  # the ingestion API's cap


def _base_range(env: Mapping[str, str], commit: Optional[str]) -> Optional[tuple]:
    """(base_ref label, git range). Branch bases use triple-dot (merge-base diff)."""
    github_base = (env.get("GITHUB_BASE_REF") or "").strip()
    if github_base:
        base = f"origin/{github_base}"
        return base, f"{base}...HEAD"
    gitlab_base = (env.get("CI_MERGE_REQUEST_TARGET_BRANCH_NAME") or "").strip()
    if gitlab_base:
        base = f"origin/{gitlab_base}"
        return base, f"{base}...HEAD"
    if commit:
        return f"{commit}^", f"{commit}^..{commit}"
    return None


def _git(run: Callable, args: list) -> str:
    completed = run(
        ["git"] + args,
        capture_output=True, text=True, check=True, timeout=30,
    )
    return completed.stdout or ""


def _parse_numstat(raw: str) -> dict:
    """path -> (additions, deletions); '-' (binary) becomes None. Rename records
    carry an empty path followed by old and new paths; the new path wins."""
    stats = {}
    fields = raw.split("\0")
    i = 0
    while i < len(fields):
        record = fields[i]
        if not record.strip():
            i += 1
            continue
        adds, dels, path = (record.split("\t") + ["", ""])[:3]
        if path == "" and i + 2 < len(fields):  # rename: old\0new follow
            path = fields[i + 2]
            i += 2
        counts = (
            None if adds == "-" else int(adds),
            None if dels == "-" else int(dels),
        )
        stats[path] = counts
        i += 1
    return stats


def _parse_name_status(raw: str) -> list:
    """[(status letter, path)] with renames/copies mapped to their new path."""
    fields = [f for f in raw.split("\0")]
    out = []
    i = 0
    while i < len(fields):
        status = fields[i].strip()
        if not status:
            i += 1
            continue
        letter = status[0]
        if letter in ("R", "C") and i + 2 < len(fields):
            out.append((letter, fields[i + 2]))
            i += 3
        elif i + 1 < len(fields):
            out.append((letter, fields[i + 1]))
            i += 2
        else:
            break
    return out


def collect_changes(
    env: Mapping[str, str],
    commit: Optional[str],
    *,
    run: Callable = subprocess.run,
) -> Optional[dict]:
    resolved = _base_range(env, commit)
    if resolved is None:
        return None
    base_ref, diff_range = resolved
    try:
        numstat = _parse_numstat(_git(run, ["diff", "--numstat", "-z", diff_range]))
        names = _parse_name_status(_git(run, ["diff", "--name-status", "-z", diff_range]))
    except Exception:
        return None

    truncated = len(names) > MAX_FILES
    files = []
    for letter, path in names[:MAX_FILES]:
        adds, dels = numstat.get(path, (None, None))
        files.append({"path": path, "status": letter, "additions": adds, "deletions": dels})
    return {"base_ref": base_ref, "truncated": truncated, "files": files}


def collect_commit_info(
    commit: Optional[str], *, run: Callable = subprocess.run
) -> tuple:
    """(author, subject) of the commit; (None, None) on any failure."""
    if not commit:
        return None, None
    try:
        out = _git(run, ["log", "-1", "--format=%an%n%s", commit])
    except Exception:
        return None, None
    lines = out.splitlines()
    author = lines[0].strip() if lines else ""
    subject = lines[1].strip() if len(lines) > 1 else ""
    return (author or None, subject or None)
