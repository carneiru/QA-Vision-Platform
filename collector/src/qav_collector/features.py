"""qav-collector import-features: keep test cases in sync with the repository's .feature files.

The API key is traded for a 5-minute import token (ADR-024); the import is full by default, so
cases of deleted files are archived, and the server refuses a mass archive unless allowed."""
from __future__ import annotations

import glob
import http.client
import json
import os
from typing import Callable, Dict, List, Mapping, Optional

from qav_collector.ci import detect
from qav_collector.config_file import load_config
from qav_collector.upload import COLLECT_PATH, ConfigError, _send, endpoint_for, make_context

TOKEN_PATH = "/api/v1/collect/token"
DEFAULT_BRANCH = "master"
DEFAULT_PATTERNS = ["**/*.feature"]
SHOWN_ERRORS = 5


class ImportFailed(Exception):
    pass


def base_url(url: str) -> str:
    return endpoint_for(url)[: -len(COLLECT_PATH)]


def collect_files(patterns: List[str], cwd: str) -> List[Dict[str, str]]:
    paths = sorted({os.path.normpath(p) for pattern in patterns
                    for p in glob.glob(os.path.join(cwd, pattern), recursive=True) if os.path.isfile(p)})
    files = []
    for path in paths:
        relative = os.path.relpath(path, cwd).replace(os.sep, "/")
        try:
            with open(path, encoding="utf-8") as fh:
                files.append({"path": relative, "content": fh.read()})
        except (OSError, UnicodeDecodeError) as exc:
            raise ConfigError(f"cannot read {relative} as UTF-8 text: {exc}") from exc
    return files


def _detail(raw: bytes) -> str:
    try:
        detail = json.loads(raw or b"{}").get("detail")
    except (ValueError, AttributeError):
        return raw[:200].decode("utf-8", "replace")
    if isinstance(detail, dict):
        return str(detail.get("message") or detail)
    return str(detail)


def _post(url: str, body: bytes, token: str, context) -> tuple:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        return _send(url, body, headers, context)
    except (OSError, http.client.HTTPException) as exc:
        raise ImportFailed(f"cannot reach {url.split('/api/')[0]}: {exc}") from exc


def trade_key(base: str, api_key: str, context) -> dict:
    status, raw, _ = _post(base + TOKEN_PATH, b"{}", api_key, context)
    if status == 200:
        return json.loads(raw)
    if status == 401:
        raise ImportFailed("the API key is invalid or revoked (401)")
    raise ImportFailed(f"the token request answered {status}: {_detail(raw)}")


def run_import(base: str, grant: dict, files: list, *, full: bool, allow_mass_archive: bool,
               dry_run: bool, context) -> dict:
    payload = {"files": files, "full": full}
    if allow_mass_archive:
        payload["allow_mass_archive"] = True
    url = f"{base}/api/v1/projects/{grant['project_id']}/cases/import?dry_run={'true' if dry_run else 'false'}"
    status, raw, _ = _post(url, json.dumps(payload).encode("utf-8"), grant["token"], context)
    if status == 200:
        return json.loads(raw)
    raise ImportFailed(f"the import answered {status}: {_detail(raw)}")


def report(result: dict, say: Callable[[str], None], dry_run: bool) -> None:
    s = result["summary"]
    verb = "would import" if dry_run else "imported"
    say(f"{verb}: {s['created']} created, {s['updated']} updated, {s['moved']} moved, "
        f"{s['reactivated']} reactivated, {s['archived']} archived, {s['unchanged']} unchanged, "
        f"{s['skipped']} skipped")
    if dry_run:
        for item in result["items"]:
            if item["action"] != "unchanged":
                say(f"  {item['action']:<10} {item['path']}  {item['scenario'] or ''}".rstrip())
    for error in result["errors"][:SHOWN_ERRORS]:
        line = f":{error['line']}" if error.get("line") else ""
        say(f"  error {error['path']}{line} {error['message']}")
    if len(result["errors"]) > SHOWN_ERRORS:
        say(f"  ... and {len(result['errors']) - SHOWN_ERRORS} more errors")
    if result["warnings"]:
        say(f"  {len(result['warnings'])} warnings (skipped scenarios or tags)")


def run(args, env: Mapping[str, str], api_key: str, say: Callable[[str], None], cwd: str) -> int:
    config = load_config(cwd)
    url: Optional[str] = args.url or env.get("QAV_URL") or config.get("url")
    if not url:
        raise ConfigError("no platform URL: pass --url, set QAV_URL, or add url to .qav.yml")
    if not api_key:
        raise ConfigError("QAV_API_KEY is not set")
    sync_branch = args.branch or env.get("QAV_IMPORT_BRANCH") or DEFAULT_BRANCH
    current = detect(env).branch
    if current and current != sync_branch:
        say(f"skipped: on {current}; cases sync from {sync_branch}")
        return 0
    patterns = args.patterns or config.get("features") or DEFAULT_PATTERNS
    files = collect_files(list(patterns), cwd)
    if not files:
        raise ConfigError(f"no .feature files match {', '.join(patterns)}")
    context = make_context(args.ca_file or env.get("QAV_CA_FILE") or config.get("ca-file"))
    base = base_url(url)
    try:
        grant = trade_key(base, api_key, context)
        result = run_import(base, grant, files, full=not args.no_full,
                            allow_mass_archive=args.allow_mass_archive, dry_run=args.dry_run, context=context)
    except ImportFailed as exc:
        say(str(exc))
        return 1
    report(result, say, args.dry_run)
    return 1 if result["errors"] and args.strict else 0
