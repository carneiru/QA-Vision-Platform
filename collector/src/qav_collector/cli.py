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
from qav_collector.codeowners import load_codeowners
from qav_collector.config_file import load_config
from qav_collector.formats import parse_file
from qav_collector.gitdiff import collect_changes, collect_commit_info
from qav_collector.payload import build_parts, build_run, parse_components, run_times, summarize
from qav_collector.spool import spool_part, spooled_parts
from qav_collector.upload import (
    ConfigError, UploadError, check_key, endpoint_for, make_context, upload_part,
)

CI_PROVIDERS = ("github_actions", "gitlab_ci", "jenkins", "azure_pipelines", "other", "local")
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
    upload.add_argument("patterns", nargs="*", metavar="PATTERN",
                        help="default: the patterns list in .qav.yml")
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
    upload.add_argument("--gate", action="store_true",
                        help="exit 1 when the run has failures outside quarantine, or when it could not be "
                             "uploaded (default: $QAV_GATE)")
    upload.add_argument("--no-changes", action="store_true",
                        help="skip git code-change collection (default: $QAV_NO_CHANGES)")
    upload.add_argument("--client-cert", help="client certificate for mTLS (default: $QAV_CLIENT_CERT)")
    upload.add_argument("--client-key", help="private key for --client-cert (default: $QAV_CLIENT_KEY)")
    upload.add_argument("--spool", metavar="DIR",
                        help="keep parts a failed upload could not deliver in DIR and resend them on "
                             "the next invocation (default: $QAV_SPOOL)")
    upload.add_argument("--dry-run", action="store_true", help="print the JSON that would be sent; upload nothing")
    check = commands.add_parser(
        "check",
        help="verify the configuration without uploading: URL, TLS, API key, and report parsing",
        description="Verify the collector can talk to the platform: URL shape, TLS trust, API key. "
        "With PATTERN arguments, also checks that reports match and parse. Uploads nothing. "
        "Exits 2 on the first failed check.",
    )
    check.add_argument("patterns", nargs="*", metavar="PATTERN")
    check.add_argument("--url", help="platform URL (default: $QAV_URL)")
    check.add_argument("--ca-file", help="trust exactly this CA certificate (default: $QAV_CA_FILE)")
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
    if args.command == "check":
        # A diagnostic: any failure is the answer, so it always exits 2, never softened
        try:
            return _check(args, env, api_key, say)
        except (ConfigError, UploadError) as exc:
            say(str(exc))
            return 2
    fail_on_error = args.fail_on_error or env.get("QAV_FAIL_ON_ERROR", "").strip().lower() in _TRUE
    gate = args.gate or env.get("QAV_GATE", "").strip().lower() in _TRUE
    if not (fail_on_error and gate):
        try:
            file_config = load_config(os.getcwd())
            fail_on_error = fail_on_error or file_config.get("fail-on-error") is True
            gate = gate or file_config.get("gate") is True
        except ConfigError:
            pass  # _upload reads the file itself and reports the problem properly
    try:
        receipt = _upload(args, env, api_key, say, now=now, sleep=sleep, clock=clock)
        if isinstance(receipt, int):  # dry run, or nothing to upload
            return receipt
        return _gate(receipt, say) if gate else 0
    except ConfigError as exc:
        say(str(exc))
        return 2
    except _UploadFailed:
        pass
    except Exception as exc:  # a bug in the collector must not break the build either
        say(f"unexpected error: {type(exc).__name__}: {exc}")
    if gate:
        say("gate failed: the gate cannot pass without an upload")
        return 1
    if fail_on_error:
        return 1
    say("not failing the build (pass --fail-on-error to change that)")
    return 0


def _gate(receipt: dict, say: _Output) -> int:
    """The run's verdict for CI: failures of quarantined tests do not count."""
    if "blocking" in receipt:
        blocking, held = int(receipt["blocking"]), int(receipt.get("quarantined", 0))
    else:
        say("the platform does not report quarantine; every failure counts")
        blocking, held = int(receipt.get("failed", 0)) + int(receipt.get("errored", 0)), 0
    if blocking > 0:
        say(f"gate failed: {blocking} failing test(s) outside quarantine"
            + (f", {held} more in quarantine" if held else ""))
        return 1
    say(f"gate passed: {held} failure(s) in quarantine, not counted" if held else "gate passed: no failures")
    return 0


def _check(args, env: Mapping[str, str], api_key: str, say: _Output) -> int:
    def pick(flag: Optional[str], name: str) -> Optional[str]:
        return (flag or "").strip() or env.get(name, "").strip() or None

    url = pick(args.url, "QAV_URL")
    if not url:
        raise ConfigError("QAV_URL is not set (or pass --url)")
    endpoint_for(url)  # validates the shape; raises ConfigError
    say(f"url: ok ({url})")

    if not api_key:
        raise ConfigError("QAV_API_KEY is not set; the API key is read from the environment only")
    if not _API_KEY.match(api_key):
        raise ConfigError("QAV_API_KEY must be printable ASCII without spaces; check the CI secret")
    context = make_context(pick(args.ca_file, "QAV_CA_FILE"))
    identity = check_key(url, api_key, context)
    say(f"key: ok (project {identity.get('project_id', '?')}, key {identity.get('name', '?')!r})")

    if args.patterns:
        files = _expand(args.patterns)
        if not files:
            raise ConfigError(f"no file matched {' '.join(args.patterns)}")
        parsed = [parse_file(path) for path in files]
        for report in parsed:
            for warning in report.warnings:
                say(warning)
        results = [result for report in parsed for result in report.results]
        say(f"reports: {sum(1 for report in parsed if not report.skipped)} file(s), {len(results)} results")
    return 0


def _upload(args, env: Mapping[str, str], api_key: str, say: _Output, *, now, sleep, clock) -> "int | dict":
    """The last receipt after an upload; an exit code when nothing was uploaded."""
    file_config = load_config(os.getcwd())

    def from_file(key: str) -> Optional[str]:
        value = file_config.get(key)
        return value if isinstance(value, str) else None

    def pick(flag: Optional[str], name: str, detected: Optional[str] = None,
             file_key: Optional[str] = None) -> Optional[str]:
        # Precedence: flag, then environment, then .qav.yml, then detection
        return ((flag or "").strip() or env.get(name, "").strip()
                or (from_file(file_key) if file_key else None) or detected)

    endpoint, context = "", None
    if not args.dry_run:
        url = pick(args.url, "QAV_URL", file_key="url")
        if not url:
            raise ConfigError("QAV_URL is not set (or pass --url, or url: in .qav.yml)")
        if not api_key:
            raise ConfigError("QAV_API_KEY is not set; the API key is read from the environment only")
        if not _API_KEY.match(api_key):
            # Checked here because http.client would otherwise reject the header with an error that
            # quotes the key in a form the output scrubbing does not recognise
            raise ConfigError("QAV_API_KEY must be printable ASCII without spaces; check the CI secret")
        endpoint = endpoint_for(url)
        context = make_context(
            pick(args.ca_file, "QAV_CA_FILE", file_key="ca-file"),
            client_cert=pick(args.client_cert, "QAV_CLIENT_CERT"),
            client_key=pick(args.client_key, "QAV_CLIENT_KEY"),
        )

    ci = detect(env)
    provider = pick(args.ci_provider, "QAV_CI_PROVIDER", ci.provider, file_key="ci-provider")
    if provider not in CI_PROVIDERS:
        raise ConfigError(f"QAV_CI_PROVIDER must be one of {', '.join(CI_PROVIDERS)}, got {provider!r}")

    patterns = args.patterns or list(file_config.get("patterns") or [])
    if not patterns:
        raise ConfigError("no report patterns given (arguments, or patterns: in .qav.yml)")
    files = _expand(patterns)
    if not files:
        raise ConfigError(f"no file matched {' '.join(patterns)}")
    parsed = [parse_file(path) for path in files]
    for report in parsed:
        for warning in report.warnings:
            say(warning)
    results = [result for report in parsed for result in report.results]
    if not results:
        say("no test results found")
        return 0

    owners_for = load_codeowners(os.getcwd())
    owned = 0
    for result in results:
        owner = owners_for(result["file"]) if result.get("file") else None
        if owner:
            result["owner"] = owner
            owned += 1
    if owned:
        say(f"owners from CODEOWNERS on {owned} result(s)")

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
        branch=pick(args.branch, "QAV_BRANCH", ci.branch, file_key="branch"),
        environment=pick(args.environment, "QAV_ENVIRONMENT", file_key="environment"),
        commit_author=author,
        commit_message=subject,
        pr_number=ci.pr_number,
        base_branch=ci.base_branch,
    )
    changes = None
    skip_changes = (args.no_changes or env.get("QAV_NO_CHANGES", "").strip().lower() in _TRUE
                    or file_config.get("no-changes") is True)
    if not skip_changes:
        changes = collect_changes(env, run.get("commit_sha"))
        if changes is not None:
            adds = sum(f["additions"] or 0 for f in changes["files"])
            dels = sum(f["deletions"] or 0 for f in changes["files"])
            say(f"changes vs {changes['base_ref']}: {len(changes['files'])} file(s), +{adds} -{dels}"
                + (" (truncated)" if changes["truncated"] else ""))

    component_values = (args.component
                        or [v for v in env.get("QAV_COMPONENTS", "").split(",") if v.strip()]
                        or list(file_config.get("components") or []))
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

    spool_dir = pick(args.spool, "QAV_SPOOL", file_key="spool")
    if spool_dir:
        _resend_spooled(spool_dir, endpoint, api_key, context, say, sleep=sleep, clock=clock)

    stored: List[str] = []
    for number, part in enumerate(parts, start=1):
        of = f"part {number} of {len(parts)}"
        try:
            status, receipt = upload_part(endpoint, api_key, part, context, sleep=sleep, clock=clock)
        except UploadError as exc:
            say(f"upload failed: {exc}")
            if stored:
                say(f"stored before the failure: {', '.join(stored)}")
            if spool_dir and exc.retryable:
                # This part and every later one: a 409 on a later part out of order is worse
                # than retrying all of them under their original keys
                spooled = sum(1 for p in parts[number - 1:] if spool_part(spool_dir, p) is not None)
                say(f"spooled {spooled} part(s) for the next run")
            raise _UploadFailed() from None
        run_id = receipt.get("id", "?")
        say(f"uploaded run {run_id} ({status})" + (f", {of}" if len(parts) > 1 else ""))
        stored.append(f"run {run_id} ({of})")
    # The last part's receipt counts the whole run: the gate reads it
    return receipt


def _resend_spooled(spool_dir, endpoint, api_key, context, say: _Output, *, sleep, clock) -> None:
    """Best effort before the current run: a still-broken platform keeps the
    files, a non-retryable answer (replayed key, revoked access) drops them."""
    resent = 0
    for path, part in spooled_parts(spool_dir):
        try:
            upload_part(endpoint, api_key, part, context, sleep=sleep, clock=clock)
        except UploadError as exc:
            if exc.retryable:
                say(f"a spooled part still fails: {exc}")
                continue
            say(f"dropping a spooled part the platform will never take: {exc}")
        else:
            resent += 1
        try:
            path.unlink()
        except OSError:
            pass
    if resent:
        say(f"resent {resent} spooled part(s)")


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
