"""qav-collector command line: parse JUnit XML reports and upload them as one run."""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, List, Mapping, Optional, Sequence

from qav_collector import __version__
from qav_collector.ci import detect, sanitize_key
from qav_collector.junit import parse_file
from qav_collector.gitdiff import collect_changes, collect_commit_info
from qav_collector.payload import build_parts, build_run, parse_components, run_times, summarize
from qav_collector.upload import ConfigError, UploadError, endpoint_for, make_context, upload_part

CI_PROVIDERS = ("github_actions", "gitlab_ci", "jenkins", "other", "local")
_TRUE = ("1", "true", "yes")
_API_KEY = re.compile(r"^[\x21-\x7e]+$")


class _UploadFailed(Exception):
    pass


class _Output:
    """One stderr line per message, prefixed "qav:"; the API key never reaches them."""

    def __init__(self, secret: str):
        self.secret = secret

    def __call__(self, message: str) -> None:
        if self.secret:
            message = message.replace(self.secret, "***")
        line = f"qav: {message}"
        try:
            print(line, file=sys.stderr)
        except UnicodeEncodeError:  # a console that cannot show the characters
            print(line.encode("ascii", "backslashreplace").decode("ascii"), file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qav-collector", description="Upload JUnit XML test results to the QA Vision platform."
    )
    parser.add_argument("--version", action="version", version=f"qav-collector {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    upload = commands.add_parser(
        "upload",
        help="parse JUnit XML files and upload them as one run",
        description="Parse the JUnit XML files matching PATTERN (** matches any directories) and upload "
        "them as one run. The API key is read from the QAV_API_KEY environment variable only.",
    )
    upload.add_argument("patterns", nargs="+", metavar="PATTERN")
    upload.add_argument("--url", help="platform URL (default: $QAV_URL)")
    upload.add_argument("--ci-provider", choices=CI_PROVIDERS, help="default: $QAV_CI_PROVIDER, else detected")
    upload.add_argument("--branch", help="default: $QAV_BRANCH, else detected")
    upload.add_argument("--commit", help="full or short SHA (default: $QAV_COMMIT, else detected)")
    upload.add_argument("--ci-run-url", help="default: $QAV_CI_RUN_URL, else detected")
    upload.add_argument("--environment", help="e.g. staging (default: $QAV_ENVIRONMENT)")
    upload.add_argument("--idempotency-key", help="default: $QAV_IDEMPOTENCY_KEY, else derived from the CI job")
    upload.add_argument("--ca-file", help="trust exactly this CA certificate, e.g. a private or self-signed one (default: $QAV_CA_FILE)")
    upload.add_argument("--component", action="append", default=[], metavar="NAME@SHA",
                        help="a repo/version this run exercised, e.g. product-api@3f2a9c1; repeatable "
                             "(default: $QAV_COMPONENTS, comma separated)")
    upload.add_argument("--fail-on-error", action="store_true",
                        help="exit 1 if the upload fails (default: $QAV_FAIL_ON_ERROR)")
    upload.add_argument("--no-changes", action="store_true",
                        help="skip git code-change collection (default: $QAV_NO_CHANGES)")
    upload.add_argument("--dry-run", action="store_true", help="print the JSON that would be sent; upload nothing")
    return parser


def main(
    argv: Optional[Sequence[str]] = None,
    env: Optional[Mapping[str, str]] = None,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    env = os.environ if env is None else env
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help, --version, usage errors
        return exc.code if isinstance(exc.code, int) else 2
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2

    api_key = env.get("QAV_API_KEY", "").strip()
    say = _Output(api_key)
    fail_on_error = args.fail_on_error or env.get("QAV_FAIL_ON_ERROR", "").strip().lower() in _TRUE
    try:
        return _upload(args, env, api_key, say, now=now, sleep=sleep, clock=clock)
    except ConfigError as exc:
        say(str(exc))
        return 2
    except _UploadFailed:
        pass
    except Exception as exc:  # a bug in the collector must not break the build either
        say(f"unexpected error: {type(exc).__name__}: {exc}")
    if fail_on_error:
        return 1
    say("not failing the build (pass --fail-on-error to change that)")
    return 0


def _upload(args, env: Mapping[str, str], api_key: str, say: _Output, *, now, sleep, clock) -> int:
    def pick(flag: Optional[str], name: str, detected: Optional[str] = None) -> Optional[str]:
        return (flag or "").strip() or env.get(name, "").strip() or detected

    endpoint, context = "", None
    if not args.dry_run:
        url = pick(args.url, "QAV_URL")
        if not url:
            raise ConfigError("QAV_URL is not set (or pass --url)")
        if not api_key:
            raise ConfigError("QAV_API_KEY is not set; the API key is read from the environment only")
        if not _API_KEY.match(api_key):
            # Checked here because http.client would otherwise reject the header with an error that
            # quotes the key in a form the output scrubbing does not recognise
            raise ConfigError("QAV_API_KEY must be printable ASCII without spaces; check the CI secret")
        endpoint = endpoint_for(url)
        context = make_context(pick(args.ca_file, "QAV_CA_FILE"))

    ci = detect(env)
    provider = pick(args.ci_provider, "QAV_CI_PROVIDER", ci.provider)
    if provider not in CI_PROVIDERS:
        raise ConfigError(f"QAV_CI_PROVIDER must be one of {', '.join(CI_PROVIDERS)}, got {provider!r}")

    files = _expand(args.patterns)
    if not files:
        raise ConfigError(f"no file matched {' '.join(args.patterns)}")
    parsed = [parse_file(path) for path in files]
    for report in parsed:
        for warning in report.warnings:
            say(warning)
    results = [result for report in parsed for result in report.results]
    if not results:
        say("no test results found")
        return 0
    counts = summarize(results)
    say(
        f"parsed {sum(1 for report in parsed if not report.skipped)} file(s), {len(results)} results "
        f"({counts['failed']} failed, {counts['errored']} errored, {counts['skipped']} skipped)"
    )

    author, subject = collect_commit_info(pick(args.commit, "QAV_COMMIT", ci.commit))

    started, finished = run_times(
        [stamp for report in parsed for stamp in report.suite_timestamps],
        sum(report.suite_seconds for report in parsed),
        results,
        now(),
    )
    run = build_run(
        ci_provider=provider,
        started_at=started,
        finished_at=finished,
        ci_run_url=pick(args.ci_run_url, "QAV_CI_RUN_URL", ci.run_url),
        commit_sha=pick(args.commit, "QAV_COMMIT", ci.commit),
        branch=pick(args.branch, "QAV_BRANCH", ci.branch),
        environment=pick(args.environment, "QAV_ENVIRONMENT"),
        commit_author=author,
        commit_message=subject,
        pr_number=ci.pr_number,
        base_branch=ci.base_branch,
    )
    changes = None
    skip_changes = args.no_changes or env.get("QAV_NO_CHANGES", "").strip().lower() in _TRUE
    if not skip_changes:
        changes = collect_changes(env, run.get("commit_sha"))
        if changes is not None:
            adds = sum(f["additions"] or 0 for f in changes["files"])
            dels = sum(f["deletions"] or 0 for f in changes["files"])
            say(f"changes vs {changes['base_ref']}: {len(changes['files'])} file(s), +{adds} -{dels}"
                + (" (truncated)" if changes["truncated"] else ""))

    component_values = args.component or [v for v in env.get("QAV_COMPONENTS", "").split(",") if v.strip()]
    try:
        components = parse_components(component_values)
    except ValueError as exc:
        raise ConfigError(str(exc)) from None
    if components:
        say("components under test: " + ", ".join(f"{c['name']}@{c['sha'][:12]}" for c in components))

    key = sanitize_key(pick(args.idempotency_key, "QAV_IDEMPOTENCY_KEY") or "")
    if not key:
        # The CI identifiers name the job, but every leg of a matrix and every upload step in one
        # job share them, and the server answers 409 when a key comes back with a different body
        # (finished_at alone always differs). So each invocation adds its own random suffix: the
        # collector's retries reuse the key, and a POST stored without an answer is replayed.
        key = f"{ci.idempotency_key or 'local'}-{uuid.uuid4().hex[:12]}"
    parts = build_parts(run, results, key, changes, components)

    if args.dry_run:
        for part in parts:
            print(json.dumps(json.loads(part.body), indent=2))
        say(f"dry run: {len(parts)} part(s), nothing uploaded")
        return 0

    stored: List[str] = []
    for number, part in enumerate(parts, start=1):
        of = f"part {number} of {len(parts)}"
        try:
            status, receipt = upload_part(endpoint, api_key, part, context, sleep=sleep, clock=clock)
        except UploadError as exc:
            say(f"upload failed: {exc}")
            if stored:
                say(f"stored before the failure: {', '.join(stored)}")
            raise _UploadFailed() from None
        run_id = receipt.get("id", "?")
        say(f"uploaded run {run_id} ({status})" + (f", {of}" if len(parts) > 1 else ""))
        stored.append(f"run {run_id} ({of})")
    return 0


def _expand(patterns: Sequence[str]) -> List[str]:
    files: List[str] = []
    seen = set()
    for pattern in patterns:
        for path in sorted(glob.glob(pattern, recursive=True)):
            identity = os.path.normcase(os.path.realpath(path))
            if os.path.isfile(path) and identity not in seen:
                seen.add(identity)
                files.append(path)
    return files
