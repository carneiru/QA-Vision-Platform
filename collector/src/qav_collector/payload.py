"""The upload body: run times, run metadata, and splitting into parts the server accepts."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from qav_collector import __version__

MAX_RESULTS_PER_PART = 20000
# The gateway accepts bodies up to 10 MB
MAX_PART_BYTES = 9 * 1024 * 1024
MAX_RUN_SPAN = timedelta(days=7)
BRANCH_LENGTH = 255
ENVIRONMENT_LENGTH = 100
RUN_URL_LENGTH = 2048
_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")
_RUN_URL = re.compile(r"^https?://\S+$")


@dataclass
class Part:
    body: bytes
    idempotency_key: str
    count: int


def run_times(
    timestamps: Sequence[datetime], suite_seconds: float, results: Sequence[dict], now: datetime
) -> Tuple[datetime, datetime]:
    finished = now
    if timestamps:
        started = min(timestamps)
    else:
        seconds = suite_seconds if suite_seconds > 0 else sum(r["duration_ms"] for r in results) / 1000
        started = finished - timedelta(seconds=min(seconds, MAX_RUN_SPAN.total_seconds()))
    # The server rejects runs longer than 7 days and starts after the finish
    started = min(max(started, finished - MAX_RUN_SPAN), finished)
    return started, finished


def build_run(
    *,
    ci_provider: str,
    started_at: datetime,
    finished_at: datetime,
    ci_run_url: Optional[str] = None,
    commit_sha: Optional[str] = None,
    branch: Optional[str] = None,
    environment: Optional[str] = None,
) -> Dict[str, str]:
    """Metadata the server would reject is left out or cut, so it never costs the whole run."""
    run = {
        "ci_provider": ci_provider,
        "agent_version": f"qav-collector/{__version__}",
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "finished_at": finished_at.astimezone(timezone.utc).isoformat(),
    }
    ci_run_url, commit_sha = _storable(ci_run_url), _storable(commit_sha)
    branch, environment = _storable(branch), _storable(environment)
    if ci_run_url and len(ci_run_url) <= RUN_URL_LENGTH and _RUN_URL.match(ci_run_url):
        run["ci_run_url"] = ci_run_url
    if commit_sha and _SHA.match(commit_sha):
        run["commit_sha"] = commit_sha
    if branch:
        run["branch"] = branch[:BRANCH_LENGTH]
    if environment:
        run["environment"] = environment[:ENVIRONMENT_LENGTH]
    return run


def build_parts(run: dict, results: List[dict], idempotency_key: str,
                changes: "dict | None" = None) -> List[Part]:
    chunks = [results[i:i + MAX_RESULTS_PER_PART] for i in range(0, len(results), MAX_RESULTS_PER_PART)]
    encoded: List[Tuple[bytes, int]] = []
    for chunk in chunks:
        encoded.extend(_fit(run, chunk, changes))
    if len(encoded) == 1:
        body, count = encoded[0]
        return [Part(body=body, idempotency_key=idempotency_key, count=count)]
    # Numbered keys, so a re-run of the same CI job replays exactly the same parts
    return [
        Part(body=body, idempotency_key=f"{idempotency_key}-part-{number}", count=count)
        for number, (body, count) in enumerate(encoded, start=1)
    ]


def summarize(results: Sequence[dict]) -> Dict[str, int]:
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errored": 0}
    for result in results:
        counts[result["status"]] += 1
    return counts


def _fit(run: dict, chunk: List[dict], changes: "dict | None" = None) -> List[Tuple[bytes, int]]:
    payload = {"run": run, "results": chunk}
    if changes is not None:
        payload["changes"] = changes
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) <= MAX_PART_BYTES or len(chunk) == 1:
        return [(body, len(chunk))]
    middle = len(chunk) // 2
    return _fit(run, chunk[:middle], changes) + _fit(run, chunk[middle:], changes)


def _storable(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    # Lone surrogates (undecodable bytes in os.environ or argv) become "?"
    return value.encode("utf-8", errors="replace").decode("utf-8").strip() or None
