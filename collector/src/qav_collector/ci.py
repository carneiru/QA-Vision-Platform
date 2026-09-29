"""Run metadata from the CI system's environment variables."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

# The server takes Idempotency-Keys up to 255 characters; this leaves room for "-part-N"
MAX_KEY_LENGTH = 200


@dataclass
class CIInfo:
    provider: str
    commit: Optional[str] = None
    branch: Optional[str] = None
    run_url: Optional[str] = None
    idempotency_key: Optional[str] = None


def detect(env: Mapping[str, str]) -> CIInfo:
    def get(name: str) -> Optional[str]:
        return env.get(name, "").strip() or None

    if get("GITHUB_ACTIONS") == "true":
        server, repo, run_id = get("GITHUB_SERVER_URL"), get("GITHUB_REPOSITORY"), get("GITHUB_RUN_ID")
        return CIInfo(
            provider="github_actions",
            commit=get("GITHUB_SHA"),
            # On pull requests GITHUB_REF_NAME is "<number>/merge"; the head branch is the useful one
            branch=get("GITHUB_HEAD_REF") or get("GITHUB_REF_NAME"),
            run_url=f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else None,
            # A re-run attempt is a new execution, so it gets a new key on purpose
            idempotency_key=_key("gh", run_id, get("GITHUB_RUN_ATTEMPT") or "1", get("GITHUB_JOB")) if run_id else None,
        )
    if get("GITLAB_CI") == "true":
        job_id = get("CI_JOB_ID")
        return CIInfo(
            provider="gitlab_ci",
            commit=get("CI_COMMIT_SHA"),
            branch=get("CI_COMMIT_REF_NAME"),
            run_url=get("CI_JOB_URL"),
            idempotency_key=_key("gl", job_id) if job_id else None,
        )
    if get("JENKINS_URL"):
        branch, tag = get("GIT_BRANCH"), get("BUILD_TAG")
        if branch and branch.startswith("origin/"):
            branch = branch[len("origin/"):]
        return CIInfo(
            provider="jenkins",
            commit=get("GIT_COMMIT"),
            branch=branch,
            run_url=get("BUILD_URL"),
            idempotency_key=_key("jk", tag) if tag else None,
        )
    return CIInfo(provider="local")


def sanitize_key(raw: str) -> Optional[str]:
    """Printable ASCII without spaces, at most MAX_KEY_LENGTH characters."""
    cleaned = "".join(c if "!" <= c <= "~" else "-" for c in raw)[:MAX_KEY_LENGTH]
    return cleaned or None


def _key(*parts: Optional[str]) -> Optional[str]:
    return sanitize_key("-".join(p for p in parts if p))
