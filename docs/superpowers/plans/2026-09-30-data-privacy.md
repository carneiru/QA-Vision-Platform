# Data Privacy (Masking and Retention) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ingestion-service masks secrets and personal data in uploaded test output before storing it, and a scheduled job deletes runs older than each project's retention period (getting the periods from a new project-service internal endpoint protected by HTTP Basic credentials).

**Architecture:** A pure `redact()` module in ingestion-service, called by `ingest()` before truncation; a `redacted` flag per stored result and a Prometheus counter. project-service gains `GET /internal/v1/projects/retention` behind HTTP Basic. ingestion-service gains `python -m src.ingestion.jobs.retention` (one pass, or `--loop`), run by a new compose service; its credentials come from a connection string.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, httpx (+ respx in tests), prometheus-client, pytest; Docker Compose; bash smoke script.

**Spec:** `docs/superpowers/specs/2026-09-30-data-privacy-design.md`

## Global Constraints

- Markers are exactly `[REDACTED:<kind>]`. Kinds: `private_key`, `authorization`, `url_password`, `jwt`, `github_token`, `gitlab_token`, `aws_access_key`, `slack_token`, `stripe_key`, `google_api_key`, `npm_token`, `qav_key`, `password`, `secret`, `token`, `api_key`, `access_key`, `client_secret`, `private_key`, `credentials`, `email`, `card_number`.
- Masking applies to `message`, `details` and `ci_run_url` only — never to `suite`, `class_name`, `name`, `file`, `branch`. Mask **before** truncating to `MAX_TEXT_BYTES`; `ci_run_url` is cut to 2048 characters after masking. The idempotency `request_hash` is computed from the upload as received.
- Masking never rejects an upload; 64 KB of hostile input must be processed in under 1 second.
- Masked values are never logged. The internal API password is never logged; URLs in logs show `user:***@host`.
- Internal endpoint: `GET /internal/v1/projects/retention` → `{"projects": [{"project_id", "result_retention_days", "deleted"}]}`; HTTP Basic against `INTERNAL_API_USERNAME` (default `ingestion-service`) / `INTERNAL_API_PASSWORD`, compared with `hmac.compare_digest`; wrong/missing → 401 with `WWW-Authenticate: Basic`; password unset → 503 `{"detail":"Internal API is not configured"}`.
- Job settings: `PROJECT_SERVICE_INTERNAL_URL` (`http://user:password@host:port`), `RETENTION_INTERVAL_HOURS` (default 24), `RETENTION_BATCH_SIZE` (default 500). A pass with no trustworthy answer deletes nothing and fails (exit 1). Projects missing from the list are never touched. Retention counts from `created_at`.
- Metric name: `qav_ingest_redactions` with label `kind` (exported `qav_ingest_redactions_total`), counting results.
- Each service's tests run from its own directory: `SECRET_KEY=x .venv/Scripts/python -m pytest tests/ -q` (Windows Git Bash; `.venv/bin/python` elsewhere). Below, `$PY` means that interpreter.
- Test fixtures build fake tokens by concatenation (`"ghp_" + ...`) so secret scanners never see a token-shaped literal in the repository.
- Git: commit as carneiru. Run `git status --short` before every `git add`; never commit stray or empty files (the local hook sometimes creates empty files named `headers`). Never push tags.

## Review Focus

1. **A non-secret key whose value hides a secret pair** (`opts=--password=x`, `"cmd": "login password=x"`): the inner secret must still be masked. Pinned by `test_a_secret_inside_another_value_is_still_masked` (Task 1).
2. **A credential-bearing `ci_run_url` close to the 2048 limit**: masking makes it longer; it must be cut, not break the insert on PostgreSQL. Pinned by `test_a_long_ci_run_url_stays_within_its_column` (Task 2).
3. **Masking run twice / markers in input** (a replayed or re-uploaded masked text): must not double-mask or report kinds again. Pinned by `test_masking_is_idempotent` (Task 1).
4. **A password with URL-special characters** (`@`, `:`, `/`) in the connection string: must be percent-decoded before use, and never appear in logs in either form. Pinned by `test_the_password_never_appears_in_the_output` (Task 4).
5. **`docker compose up gateway`** must still start the whole platform including the retention service, and the job must really reach project-service inside the stack. Pinned by the Task 5 smoke checks (`ingestion-retention is running`, `retention job dry run inside the stack`).

---

### Task 1: The redaction module

**Files:**
- Create: `platforms/ingestion-service/src/ingestion/utils/redaction.py`
- Test: `platforms/ingestion-service/tests/unit/test_redaction.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `src.ingestion.utils.redaction.redact(text: str) -> tuple[str, set[str]]` (masked text, kinds found); `marker(kind: str) -> str`; `MARKER_PREFIX = "[REDACTED:"`.

- [ ] **Step 1: Write the failing tests**

`platforms/ingestion-service/tests/unit/test_redaction.py`:

```python
import time

import pytest

from src.ingestion.utils.redaction import redact

# Built by concatenation so secret scanners never see a token-shaped literal in the repository
GH = "ghp_" + "A1b2C3d4E5" * 3 + "F6g7H8"
TOKENS = [
    ("github_token", GH),
    ("github_token", "github_pat_" + "1" * 22 + "_" + "a" * 59),
    ("gitlab_token", "glpat-" + "x" * 20),
    ("aws_access_key", "AKIA" + "IOSFODNN7EXAMPLE"),
    ("slack_token", "xoxb-" + "1234567890-abcdefghij"),
    ("stripe_key", "sk_" + "test_" + "4eC39HqLyjWDarjtT1zdp7dc"),
    ("google_api_key", "AIza" + "S" * 35),
    ("npm_token", "npm_" + "a" * 36),
    ("qav_key", "qav_" + "x" * 43),
]


@pytest.mark.parametrize("text, expected, kind", [
    ("password=hunter2", "password=[REDACTED:password]", "password"),
    ('{"password": "hunter 2"}', '{"password": "[REDACTED:password]"}', "password"),
    ("DB_PASSWORD: s3cr3t", "DB_PASSWORD: [REDACTED:password]", "password"),
    ("--password=s3cr3t", "--password=[REDACTED:password]", "password"),
    ("client_secret='abc'", "client_secret='[REDACTED:client_secret]'", "client_secret"),
    ("X-Api-Key: k123", "X-Api-Key: [REDACTED:api_key]", "api_key"),
    ("accessToken=t0k", "accessToken=[REDACTED:token]", "token"),
    ("Authorization: Bearer abc.def", "Authorization: Bearer [REDACTED:authorization]", "authorization"),
    ('"authorization": "Basic dXNlcjpwYXNz"', '"authorization": "Basic [REDACTED:authorization]"', "authorization"),
    ("connecting to postgres://app:pa55@db:5432/x",
     "connecting to postgres://app:[REDACTED:url_password]@db:5432/x", "url_password"),
    ("auth failed for eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl", "auth failed for [REDACTED:jwt]", "jwt"),
    ("mail ann.lee+qa@acme.co.uk now", "mail [REDACTED:email] now", "email"),
    ("card 4111 1111 1111 1111 ok", "card [REDACTED:card_number] ok", "card_number"),
    ("card 5555-5555-5555-4444", "card [REDACTED:card_number]", "card_number"),
    ("amex 378282246310005", "amex [REDACTED:card_number]", "card_number"),
])
def test_masked(text, expected, kind):
    assert redact(text) == (expected, {kind})


@pytest.mark.parametrize("kind, token", TOKENS)
def test_known_token_formats(kind, token):
    assert redact(f"x {token} y") == (f"x [REDACTED:{kind}] y", {kind})


@pytest.mark.parametrize("text", [
    "commit 3f2a9c1e8b7d6a5f4e3d2c1b0a9f8e7d6c5b4a39",
    "id 123e4567-e89b-12d3-a456-426614174000",
    "at 2026-09-30T12:34:56.789Z took 1727740800123 ms",
    "order 4111111111111112",
    "number 1234567812345670",
    "the password field is required",
    "PWD=/home/runner/work/shop",
    "token count: 5 tokens",
    "GET http://localhost:8000/health",
    "password=[REDACTED:password]",
    "",
])
def test_look_alikes_are_left_alone(text):
    assert redact(text) == (text, set())


def test_several_secrets_in_one_text():
    text = f"user=bob password=x1 url=https://bob:pw@h.test mail bob@h.test {GH}"
    assert redact(text) == (
        "user=bob password=[REDACTED:password] url=https://bob:[REDACTED:url_password]@h.test "
        "mail [REDACTED:email] [REDACTED:github_token]",
        {"password", "url_password", "email", "github_token"},
    )


@pytest.mark.parametrize("text, expected", [
    ("opts=--password=x", "opts=--password=[REDACTED:password]"),
    ('{"cmd": "login password=x"}', '{"cmd": "login password=[REDACTED:password]"}'),
])
def test_a_secret_inside_another_value_is_still_masked(text, expected):
    assert redact(text) == (expected, {"password"})


def test_a_private_key_block_is_masked_whole():
    text = "before\n-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nabc\n-----END RSA PRIVATE KEY-----\nafter"
    assert redact(text) == ("before\n[REDACTED:private_key]\nafter", {"private_key"})


def test_an_unterminated_private_key_is_masked_to_the_end():
    assert redact("x -----BEGIN PRIVATE KEY-----\nMIIEvQIBADAN") == ("x [REDACTED:private_key]", {"private_key"})


def test_masking_is_idempotent():
    masked, _ = redact(f"password=x1 Authorization: Bearer abc https://bob:pw@h.test {GH} ann@acme.test")
    assert redact(masked) == (masked, set())


@pytest.mark.parametrize("hostile", [
    "a" * 65536,
    "a@" * 32768,
    "a." * 32768,
    "a=" * 32768,
    "password=" * 7281,
    "1 " * 32768,
    "eyJ" * 21845,
    "x://a:" * 10922,
    'a:"' + "b" * 65533,
    "-----BEGIN PRIVATE KEY-----" * 2427,
])
def test_hostile_input_is_fast(hostile):
    start = time.perf_counter()
    redact(hostile)
    assert time.perf_counter() - start < 1.0
```

- [ ] **Step 2: Run the tests to see them fail**

Run (from `platforms/ingestion-service`): `SECRET_KEY=x $PY -m pytest tests/unit/test_redaction.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'src.ingestion.utils.redaction'`.

- [ ] **Step 3: Write the module**

`platforms/ingestion-service/src/ingestion/utils/redaction.py`:

```python
"""Masks secrets and personal data in captured test output before it is stored.

    redact(text) -> (masked text, kinds found)

The patterns run in a fixed order, and a value an earlier pattern already replaced is not matched
again. Every quantifier is bounded and none is nested in another unbounded one, so input built to
make a regular expression backtrack catastrophically cannot slow ingestion down.
"""
import re
from typing import Optional, Set, Tuple

MARKER_PREFIX = "[REDACTED:"


def marker(kind: str) -> str:
    return f"{MARKER_PREFIX}{kind}]"


_BEGIN_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY-----")
_END_PRIVATE_KEY = re.compile(r"-----END [A-Z0-9 ]{0,40}PRIVATE KEY-----")

# The value of an Authorization header; the scheme word (Bearer, Basic, ...) is kept
_AUTHORIZATION = re.compile(
    r"(?i)\b((?:proxy-)?authorization[\"']?[ \t]{0,5}[:=][ \t]{0,5}[\"']?"
    r"(?:(?:bearer|basic|token|digest)[ \t]{1,5})?)"
    r"([^\s\"',;]{1,4096})"
)

# scheme://user:password@ -- the user name is kept
_URL_PASSWORD = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]{0,20}://[^\s:/@\"'<>]{1,256}:)([^\s/@\"'<>]{1,256})(@)")

_JWT = re.compile(r"\beyJ[A-Za-z0-9_\-]{5,4096}\.eyJ[A-Za-z0-9_\-]{5,8192}\.[A-Za-z0-9_\-]{0,4096}")

_TOKENS = (
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255})\b")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,255}")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,255}")),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,255}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}(?![0-9A-Za-z_\-])")),
    ("npm_token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("qav_key", re.compile(r"\bqav_[A-Za-z0-9_\-]{43}(?![A-Za-z0-9_\-])")),
)

# key=value, key: value, "key": "value", 'key': 'value'. The key is matched as a whole word and
# then checked against _SECRET_NAMES in Python, which keeps the expression linear.
_KEY_VALUE = re.compile(
    r"(?<![A-Za-z0-9_.\-])([A-Za-z0-9_.\-]{1,64})"
    r"([\"']?[ \t]{0,5}[:=][ \t]{0,5})"
    r"(?:\"([^\"\r\n]{1,4096})\"|'([^'\r\n]{1,4096})'|([^\s,;&\"'=]{1,4096}))"
)
# (normalised key suffix, kind); longest first, so client_secret wins over secret
_SECRET_NAMES = (
    ("clientsecret", "client_secret"),
    ("credentials", "credentials"),
    ("privatekey", "private_key"),
    ("accesskey", "access_key"),
    ("password", "password"),
    ("passwd", "password"),
    ("apikey", "api_key"),
    ("secret", "secret"),
    ("token", "token"),
    ("pwd", "password"),
)
# Shell variables that hold a directory, not a password
_NOT_SECRETS = {"pwd", "oldpwd"}

_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}"
    r"(?:\.[A-Za-z0-9\-]{1,63}){0,8}\.[A-Za-z]{2,24}(?![A-Za-z0-9\-])"
)

# 13 to 19 digits, optionally grouped by single spaces or dashes; then a card prefix and Luhn
_CARD = re.compile(r"(?<![0-9])[0-9](?:[ \-]?[0-9]){12,18}(?![0-9])")


def redact(text: str) -> Tuple[str, Set[str]]:
    found: Set[str] = set()
    if not text:
        return text, found
    text = _mask_private_keys(text, found)
    text = _AUTHORIZATION.sub(lambda m: _mask_group(m, 2, "authorization", found), text)
    text = _URL_PASSWORD.sub(lambda m: _mask_group(m, 2, "url_password", found), text)
    text = _mask_all(_JWT, "jwt", text, found)
    for kind, pattern in _TOKENS:
        text = _mask_all(pattern, kind, text, found)
    text = _mask_key_values(text, found)
    text = _mask_all(_EMAIL, "email", text, found)
    text = _CARD.sub(lambda m: _mask_card(m, found), text)
    return text, found


def _mask_private_keys(text: str, found: Set[str]) -> str:
    pieces, pos = [], 0
    while True:
        begin = _BEGIN_PRIVATE_KEY.search(text, pos)
        if begin is None:
            break
        pieces.append(text[pos:begin.start()])
        pieces.append(marker("private_key"))
        found.add("private_key")
        end = _END_PRIVATE_KEY.search(text, begin.end())
        if end is None:  # no end line: the rest of the text is key material
            return "".join(pieces)
        pos = end.end()
    pieces.append(text[pos:])
    return "".join(pieces)


def _mask_group(match: "re.Match[str]", group: int, kind: str, found: Set[str]) -> str:
    if match.group(group).startswith(MARKER_PREFIX):
        return match.group(0)
    found.add(kind)
    base = match.start()
    start, end = match.span(group)
    whole = match.group(0)
    return whole[:start - base] + marker(kind) + whole[end - base:]


def _mask_all(pattern: "re.Pattern[str]", kind: str, text: str, found: Set[str]) -> str:
    def replace(_match: "re.Match[str]") -> str:
        found.add(kind)
        return marker(kind)

    return pattern.sub(replace, text)


def _secret_kind(key: str) -> Optional[str]:
    normalised = re.sub(r"[_.\-]", "", key).lower()
    if normalised in _NOT_SECRETS:
        return None
    for suffix, kind in _SECRET_NAMES:
        if normalised.endswith(suffix):
            return kind
    return None


def _mask_key_values(text: str, found: Set[str]) -> str:
    pieces, last, pos = [], 0, 0
    while True:
        match = _KEY_VALUE.search(text, pos)
        if match is None:
            break
        group = next(g for g in (3, 4, 5) if match.group(g) is not None)
        kind = _secret_kind(match.group(1))
        if kind is None or match.group(group).startswith(MARKER_PREFIX):
            # Not a secret: look again inside the value, which can hold one (opts=--password=x)
            pos = match.end(2)
            continue
        found.add(kind)
        start, end = match.span(group)  # the value only; quotes around it stay
        pieces.append(text[last:start])
        pieces.append(marker(kind))
        last = pos = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mask_card(match: "re.Match[str]", found: Set[str]) -> str:
    digits = re.sub(r"[ \-]", "", match.group(0))
    if not (_card_prefix(digits) and _luhn(digits)):
        return match.group(0)
    found.add("card_number")
    return marker("card_number")


def _card_prefix(digits: str) -> bool:
    two, four = int(digits[:2]), int(digits[:4])
    return digits[0] == "4" or 51 <= two <= 55 or 2221 <= four <= 2720 or two in (34, 37, 65) or four == 6011


def _luhn(digits: str) -> bool:
    total = 0
    for position, char in enumerate(reversed(digits)):
        n = int(char)
        if position % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/unit/test_redaction.py -q`
Expected: all pass. If one of the expected strings differs, read the actual output: a wrong expectation in a test is fixed only with a ledger ruling explaining why the actual output is the right behaviour under the spec; otherwise fix the pattern.

- [ ] **Step 5: Commit**

```bash
git status --short
git add platforms/ingestion-service/src/ingestion/utils/redaction.py platforms/ingestion-service/tests/unit/test_redaction.py
git commit -m "feat(ingestion): redact() masks secrets, emails and card numbers in text

Private keys, Authorization values, URL passwords, JWTs, well-known token
formats, secret-looking key/value pairs, emails, and card numbers that
pass Luhn. Bounded patterns only; 64 KB of hostile input in under 1 s.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Masking on ingest, the `redacted` flag and the metric

**Files:**
- Modify: `platforms/ingestion-service/src/ingestion/service/ingest_service.py`
- Modify: `platforms/ingestion-service/src/ingestion/models/run.py` (RunResult)
- Modify: `platforms/ingestion-service/src/ingestion/schemas/run.py` (ResultOut)
- Modify: `platforms/ingestion-service/src/ingestion/utils/metrics.py`
- Create: `platforms/ingestion-service/alembic/versions/002_add_redacted_to_test_results.py`
- Test: `platforms/ingestion-service/tests/integration/test_masking_on_ingest.py`, `platforms/ingestion-service/tests/unit/test_migration.py`

**Interfaces:**
- Consumes: `redact(text) -> (str, set[str])` (Task 1).
- Produces: `RunResult.redacted: bool` (column `test_results.redacted`, NOT NULL, default false); `ResultOut.redacted: bool`; `metrics.REDACTIONS` (Counter `qav_ingest_redactions`, label `kind`).

- [ ] **Step 1: Write the failing tests**

`platforms/ingestion-service/tests/integration/test_masking_on_ingest.py`:

```python
from datetime import datetime, timedelta, timezone

from src.ingestion.core.config import settings
from src.ingestion.models import Run, RunResult
from src.ingestion.utils import metrics

URL = "/api/v1/collect/runs"
GH = "ghp_" + "A1b2C3d4E5" * 3 + "F6g7H8"


def body(results, **run):
    now = datetime.now(timezone.utc)
    meta = {"ci_provider": "local", "started_at": (now - timedelta(seconds=5)).isoformat(), "finished_at": now.isoformat()}
    meta.update(run)
    return {"run": meta, "results": results}


def headers(key, idem=None):
    h = {"Authorization": f"Bearer {key}"}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def stored(db, run_id):
    return db.query(RunResult).filter_by(run_id=run_id).order_by(RunResult.id).all()


def redactions(kind):
    return metrics.REGISTRY.get_sample_value("qav_ingest_redactions_total", {"kind": kind}) or 0.0


def test_a_secret_in_the_output_is_never_stored(client, make_key, db):
    _, key = make_key()
    leak = {"name": "login", "status": "failed", "message": "login failed for ann@acme.test",
            "details": f"Authorization: Bearer abc.def\npassword=hunter2\n{GH}"}
    response = client.post(URL, json=body([leak]), headers=headers(key))
    assert response.status_code == 201
    [row] = stored(db, response.json()["id"])
    assert row.message == "login failed for [REDACTED:email]"
    for secret in ("abc.def", "hunter2", GH, "ann@acme.test"):
        assert secret not in row.details + row.message
    assert "[REDACTED:authorization]" in row.details and "[REDACTED:github_token]" in row.details
    assert row.redacted is True


def test_a_clean_result_is_not_flagged(client, make_key, db):
    _, key = make_key()
    response = client.post(URL, json=body([{"name": "ok", "status": "failed", "message": "expected 1, got 2"}]),
                           headers=headers(key))
    [row] = stored(db, response.json()["id"])
    assert row.redacted is False and row.message == "expected 1, got 2"


def test_masking_happens_before_truncation(client, make_key, db):
    _, key = make_key()
    # The token straddles the 64 KB cut: truncating first would keep its first half
    details = "x" * (settings.MAX_TEXT_BYTES - 16) + " " + GH
    response = client.post(URL, json=body([{"name": "big", "status": "failed", "details": details}]),
                           headers=headers(key))
    [row] = stored(db, response.json()["id"])
    assert "ghp_" not in row.details
    assert row.truncated is True and row.redacted is True
    assert len(row.details.encode("utf-8")) <= settings.MAX_TEXT_BYTES


def test_a_password_in_the_ci_run_url_is_masked(client, make_key, db):
    _, key = make_key()
    response = client.post(URL, json=body([{"name": "t", "status": "passed"}],
                                          ci_run_url="https://bob:s3cret@ci.acme.test/job/1"), headers=headers(key))
    run = db.get(Run, response.json()["id"])
    assert run.ci_run_url == "https://bob:[REDACTED:url_password]@ci.acme.test/job/1"


def test_a_long_ci_run_url_stays_within_its_column(client, make_key, db):
    _, key = make_key()
    url = "https://bob:x@ci.acme.test/" + "a" * (2048 - len("https://bob:x@ci.acme.test/"))
    response = client.post(URL, json=body([{"name": "t", "status": "passed"}], ci_run_url=url), headers=headers(key))
    assert response.status_code == 201
    run = db.get(Run, response.json()["id"])
    assert len(run.ci_run_url) == 2048
    assert run.ci_run_url.startswith("https://bob:[REDACTED:url_password]@ci.acme.test/")


def test_a_replay_still_matches_the_stored_run(client, make_key):
    _, key = make_key()
    upload = body([{"name": "t", "status": "failed", "details": "password=hunter2"}])
    first = client.post(URL, json=upload, headers=headers(key, "job-1"))
    second = client.post(URL, json=upload, headers=headers(key, "job-1"))
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]


def test_the_metric_counts_results_by_kind(client, make_key):
    _, key = make_key()
    before_password, before_github = redactions("password"), redactions("github_token")
    results = [
        {"name": "a", "status": "failed", "details": "password=x"},
        {"name": "b", "status": "failed", "message": "password=y", "details": f"password=z {GH}"},
        {"name": "c", "status": "passed"},
    ]
    assert client.post(URL, json=body(results), headers=headers(key)).status_code == 201
    assert redactions("password") - before_password == 2
    assert redactions("github_token") - before_github == 1


def test_the_read_api_shows_the_flag(client, make_key, auth, project_role):
    _, key = make_key(project_id=1)
    run_id = client.post(URL, json=body([{"name": "t", "status": "failed", "details": "password=x"}]),
                         headers=headers(key)).json()["id"]
    project_role("viewer", project_id=1)
    result = client.get(f"/api/v1/runs/{run_id}", headers=auth()).json()["results"][0]
    assert result["redacted"] is True and result["details"] == "password=[REDACTED:password]"
```

Add to `platforms/ingestion-service/tests/unit/test_migration.py` (at the end):

```python
def test_redacted_defaults_to_false(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(KEY), {"hash": "f" * 64})
        conn.execute(text(RUN), {"idem": None, "provider": "local"})
        conn.execute(text(
            "INSERT INTO test_results (run_id, test_key, suite, class_name, name, status, duration_ms)"
            " VALUES (1, :k, '', '', 't', 'passed', 0)"
        ), {"k": "f" * 64})
        assert conn.execute(text("SELECT redacted FROM test_results")).scalar() in (False, 0)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `SECRET_KEY=x $PY -m pytest tests/integration/test_masking_on_ingest.py tests/unit/test_migration.py -q`
Expected: failures — `AttributeError: 'RunResult' object has no attribute 'redacted'` (or the stored text still containing the secret), and `test_redacted_defaults_to_false` failing with `no such column: redacted`.

- [ ] **Step 3: Model, schema, metric, migration**

In `platforms/ingestion-service/src/ingestion/models/run.py`, after the `truncated = Column(...)` line of `RunResult`, add:

```python
    # True when masking replaced anything in message or details (see utils/redaction.py)
    redacted = Column(Boolean, nullable=False, default=False, server_default=false())
```

In `platforms/ingestion-service/src/ingestion/schemas/run.py`, in `ResultOut`, after `truncated: bool`, add:

```python
    redacted: bool
```

In `platforms/ingestion-service/src/ingestion/utils/metrics.py`, after the `DURATION = ...` line, add:

```python
REDACTIONS = Counter(
    "qav_ingest_redactions", "Results in which masking replaced a kind of secret or personal data", ["kind"],
    registry=REGISTRY,
)
```

`platforms/ingestion-service/alembic/versions/002_add_redacted_to_test_results.py`:

```python
"""add test_results.redacted

Revision ID: 002
Revises: 001
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_results",
        sa.Column("redacted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("test_results") as batch:
        batch.drop_column("redacted")
```

- [ ] **Step 4: Mask in `ingest()`**

In `platforms/ingestion-service/src/ingestion/service/ingest_service.py`:

Add to the imports:

```python
from src.ingestion.utils import metrics
from src.ingestion.utils.redaction import redact
```

Add after `truncate_utf8`:

```python
CI_RUN_URL_LENGTH = 2048


def mask(text: Optional[str]) -> tuple[Optional[str], set[str]]:
    return (None, set()) if text is None else redact(text)
```

In `ingest()`, replace `ci_run_url=meta.ci_run_url,` with `ci_run_url=ci_run_url,` and, just before `run = Run(`, add:

```python
    # Masking can lengthen the URL (the marker is longer than most passwords): cut to the column
    ci_run_url = mask(meta.ci_run_url)[0]
    if ci_run_url is not None:
        ci_run_url = ci_run_url[:CI_RUN_URL_LENGTH]
    masked_kinds: Counter = Counter()
```

Replace the start of the results loop

```python
        for result in upload.results:
            message, cut_message = truncate_utf8(result.message, settings.MAX_TEXT_BYTES)
            details, cut_details = truncate_utf8(result.details, settings.MAX_TEXT_BYTES)
```

with

```python
        for result in upload.results:
            # Mask before truncating: a cut through a secret would leave its first half unmatched
            message, message_kinds = mask(result.message)
            details, details_kinds = mask(result.details)
            kinds = message_kinds | details_kinds
            masked_kinds.update(kinds)
            message, cut_message = truncate_utf8(message, settings.MAX_TEXT_BYTES)
            details, cut_details = truncate_utf8(details, settings.MAX_TEXT_BYTES)
```

and in the row dict, after `"truncated": cut_message or cut_details,` add `"redacted": bool(kinds),`.

After `db.commit()` inside the `try` (right after `key.last_used_at = ...; db.commit()`), add:

```python
        for kind, results in masked_kinds.items():
            metrics.REDACTIONS.labels(kind=kind).inc(results)
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass (the existing suite included — the migration drift test now also covers `redacted`).

- [ ] **Step 6: Commit**

```bash
git status --short
git add platforms/ingestion-service/src platforms/ingestion-service/alembic/versions/002_add_redacted_to_test_results.py platforms/ingestion-service/tests/integration/test_masking_on_ingest.py platforms/ingestion-service/tests/unit/test_migration.py
git commit -m "feat(ingestion): mask secrets in uploaded test output before storing it

message and details are masked, then truncated; a password in ci_run_url
is masked and the URL cut to its column. Each result records whether
anything was masked (test_results.redacted, migration 002), and
qav_ingest_redactions_total counts results by kind.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: project-service internal retention endpoint

**Files:**
- Create: `platforms/project-service/src/project/api/v1/endpoints/internal.py`
- Modify: `platforms/project-service/src/project/api/main.py`
- Modify: `platforms/project-service/src/project/core/config.py`
- Modify: `platforms/project-service/README.md`
- Test: `platforms/project-service/tests/integration/test_internal_endpoints.py`

**Interfaces:**
- Consumes: `settings_view(stored) -> ProjectSettings` (existing), `Project` model (existing), `get_db` from `src.project.db.session`.
- Produces: `GET /internal/v1/projects/retention` → `{"projects": [{"project_id": int, "result_retention_days": int, "deleted": bool}]}` ordered by `project_id`; settings `INTERNAL_API_USERNAME` (default `"ingestion-service"`), `INTERNAL_API_PASSWORD` (default `""`).

- [ ] **Step 1: Write the failing tests**

`platforms/project-service/tests/integration/test_internal_endpoints.py`:

```python
import base64
from datetime import datetime, timezone

import pytest

from src.project.core.config import settings

URL = "/internal/v1/projects/retention"
PASSWORD = "internal-test-password"


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_USERNAME", "ingestion-service")
    monkeypatch.setattr(settings, "INTERNAL_API_PASSWORD", PASSWORD)


def basic(user, password):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


def test_correct_credentials_list_every_project_with_its_retention(client, configured, make_project, db):
    default = make_project(name="Default")
    custom = make_project(name="Custom")
    custom.settings = {"result_retention_days": 30}
    gone = make_project(name="Gone")
    gone.deleted_at = datetime.now(timezone.utc)
    db.commit()

    response = client.get(URL, headers=basic("ingestion-service", PASSWORD))

    assert response.status_code == 200
    assert response.json() == {"projects": [
        {"project_id": default.id, "result_retention_days": 90, "deleted": False},
        {"project_id": custom.id, "result_retention_days": 30, "deleted": False},
        {"project_id": gone.id, "result_retention_days": 90, "deleted": True},
    ]}


@pytest.mark.parametrize("headers", [
    {},
    basic("ingestion-service", "wrong"),
    basic("someone-else", PASSWORD),
    {"Authorization": "Bearer not-basic"},
])
def test_missing_or_wrong_credentials_are_401(client, configured, headers):
    response = client.get(URL, headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Basic"


def test_a_user_token_is_not_accepted(client, configured, auth):
    assert client.get(URL, headers=auth()).status_code == 401


def test_without_a_password_the_endpoint_is_off(client, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_PASSWORD", "")
    response = client.get(URL, headers=basic("ingestion-service", ""))
    assert response.status_code == 503
    assert response.json() == {"detail": "Internal API is not configured"}


def test_internal_credentials_do_not_open_the_public_api(client, configured, make_project):
    project = make_project()
    assert client.get(f"/api/v1/projects/{project.id}", headers=basic("ingestion-service", PASSWORD)).status_code == 401


def test_the_endpoint_is_not_in_the_public_openapi(client):
    assert "/internal/v1/projects/retention" not in client.get("/api/v1/openapi.json").json()["paths"]
```

- [ ] **Step 2: Run the tests to see them fail**

Run (from `platforms/project-service`): `SECRET_KEY=x $PY -m pytest tests/integration/test_internal_endpoints.py -q`
Expected: failures with 404 for the internal URL (and `AttributeError` on `settings.INTERNAL_API_PASSWORD` in the monkeypatch).

- [ ] **Step 3: Settings, endpoint, mount**

In `platforms/project-service/src/project/core/config.py`, add at the end of `Settings`:

```python
    # GET /internal/v1/projects/retention, for ingestion-service's retention job (HTTP Basic).
    # An empty password turns the endpoint off (503); it is never open by default.
    INTERNAL_API_USERNAME: str = "ingestion-service"
    INTERNAL_API_PASSWORD: str = ""
```

`platforms/project-service/src/project/api/v1/endpoints/internal.py`:

```python
"""Endpoints for other services, not for people.

Not routed by the gateway (its catch-all answers 404) and not in the public OpenAPI. Callers
authenticate with HTTP Basic: INTERNAL_API_USERNAME / INTERNAL_API_PASSWORD.
"""
import hmac
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.project.core.config import settings
from src.project.db.session import get_db
from src.project.models.project import Project
from src.project.schemas.settings import settings_view

router = APIRouter()
_basic = HTTPBasic(auto_error=False)


class ProjectRetention(BaseModel):
    project_id: int
    result_retention_days: int
    deleted: bool


class RetentionList(BaseModel):
    projects: list[ProjectRetention]


def _same(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def require_internal_caller(credentials: Optional[HTTPBasicCredentials] = Depends(_basic)) -> None:
    if not settings.INTERNAL_API_PASSWORD:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal API is not configured")
    # Both parts are always compared, so the timing does not tell which one was wrong
    user_ok = credentials is not None and _same(credentials.username, settings.INTERNAL_API_USERNAME)
    password_ok = credentials is not None and _same(credentials.password, settings.INTERNAL_API_PASSWORD)
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.get("/projects/retention", response_model=RetentionList)
def list_retention(_: None = Depends(require_internal_caller), db: Session = Depends(get_db)):
    """Every project, deleted ones included, with its effective retention period."""
    projects = db.query(Project).order_by(Project.id).all()
    return RetentionList(projects=[
        ProjectRetention(
            project_id=project.id,
            result_retention_days=settings_view(project.settings).result_retention_days,
            deleted=project.deleted_at is not None,
        )
        for project in projects
    ])
```

In `platforms/project-service/src/project/api/main.py`, change the import line `from src.project.api.v1.api import api_router` to:

```python
from src.project.api.v1.api import api_router
from src.project.api.v1.endpoints import internal
```

and after `app.include_router(api_router, prefix=settings.API_V1_STR)` add:

```python
# Service-to-service only: HTTP Basic, not routed by the gateway, not in the OpenAPI schema
app.include_router(internal.router, prefix="/internal/v1", include_in_schema=False)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 5: Document it**

In `platforms/project-service/README.md`, insert before the `## Running locally` heading:

```markdown
## Internal API

`GET /internal/v1/projects/retention` lists every project — deleted ones too — with its effective
`result_retention_days`, for ingestion-service's retention job:

```json
{"projects": [{"project_id": 7, "result_retention_days": 90, "deleted": false}]}
```

- HTTP Basic, checked against `INTERNAL_API_USERNAME` (default `ingestion-service`) and
  `INTERNAL_API_PASSWORD`. Wrong or missing credentials: 401. A user's JWT is not accepted here,
  and these credentials are accepted nowhere else.
- With `INTERNAL_API_PASSWORD` unset the endpoint answers 503 — it is never open by default.
- The gateway does not route `/internal`, and the endpoint is not in the OpenAPI schema.

```

- [ ] **Step 6: Commit**

```bash
git status --short
git add platforms/project-service/src platforms/project-service/tests/integration/test_internal_endpoints.py platforms/project-service/README.md
git commit -m "feat(project): internal endpoint listing every project's retention period

GET /internal/v1/projects/retention, behind HTTP Basic credentials from
INTERNAL_API_USERNAME/INTERNAL_API_PASSWORD (constant-time comparison);
off (503) when no password is configured; deleted projects included.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: The retention job

**Files:**
- Create: `platforms/ingestion-service/src/ingestion/jobs/__init__.py` (empty)
- Create: `platforms/ingestion-service/src/ingestion/jobs/retention.py`
- Modify: `platforms/ingestion-service/src/ingestion/core/config.py`
- Test: `platforms/ingestion-service/tests/integration/test_retention_job.py`

**Interfaces:**
- Consumes: Task 3's endpoint contract; models `ApiKey`, `Run`, `RunResult`; `SessionLocal` from `src.ingestion.db.session`; fixtures `db`, `http`, `make_key` from `tests/conftest.py`.
- Produces:
  - `src.ingestion.jobs.retention.main(argv=None, *, now=..., session_factory=None, lock_engine=None, stop=None) -> int` (exit code)
  - `run_once(*, dry_run: bool, now, session_factory, lock_engine) -> bool`
  - `parse_internal_url(value: str) -> Endpoint`, `fetch_policies(endpoint) -> list[Policy]`, `run_pass(db, policies, now, *, batch_size, dry_run) -> dict`
  - stdout summary `{"event": "retention", "projects": n, "runs_deleted": n, "keys_revoked": n, "projects_skipped": n, "dry_run": bool}`; stderr `{"event": "retention_failed", "error": "..."}`.
  - Settings `PROJECT_SERVICE_INTERNAL_URL`, `RETENTION_INTERVAL_HOURS`, `RETENTION_BATCH_SIZE`.

- [ ] **Step 1: Write the failing tests**

`platforms/ingestion-service/tests/integration/test_retention_job.py`:

```python
import base64
import json
import threading
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from src.ingestion.core.config import settings
from src.ingestion.jobs import retention
from src.ingestion.models import ApiKey, Run, RunResult

PASSWORD = "p@ss:w/rd"  # URL-special characters: the connection string carries it percent-encoded
INTERNAL = "http://ingestion-service:p%40ss%3Aw%2Frd@project-service:8000"
RETENTION_URL = "http://project-service:8000/internal/v1/projects/retention"
NOW = datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_SERVICE_INTERNAL_URL", INTERNAL)
    monkeypatch.setattr(settings, "RETENTION_BATCH_SIZE", 2)


@pytest.fixture
def session_factory(db):
    return sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)


@pytest.fixture
def answer(http):
    def _answer(projects=None, status_code=200, body=None, text=None, exc=None):
        route = http.get(RETENTION_URL, name="retention")
        if exc is not None:
            return route.mock(side_effect=exc)
        if text is not None:
            return route.mock(return_value=httpx.Response(status_code, text=text))
        payload = {"projects": projects or []} if body is None else body
        return route.mock(return_value=httpx.Response(status_code, json=payload))

    return _answer


@pytest.fixture
def add_run(db, make_key):
    keys = {}

    def _add(project_id, days_old):
        if project_id not in keys:
            keys[project_id] = make_key(project_id=project_id)[0]
        created = NOW - timedelta(days=days_old)
        run = Run(project_id=project_id, api_key_id=keys[project_id].id, request_hash="h", ci_provider="local",
                  started_at=created, finished_at=created, duration_ms=0, total=1, passed=1, failed=0,
                  skipped=0, errored=0, created_at=created)
        db.add(run)
        db.flush()
        db.add(RunResult(run_id=run.id, test_key="0" * 64, name="t", status="passed", duration_ms=1))
        db.commit()
        return run.id

    return _add


def run_job(session_factory, *args):
    return retention.main(list(args), now=lambda: NOW, session_factory=session_factory)


def remaining(db):
    db.expire_all()
    return sorted(run.id for run in db.query(Run))


def summary(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def live(project_id, days):
    return {"project_id": project_id, "result_retention_days": days, "deleted": False}


def test_runs_older_than_the_retention_period_are_deleted(db, session_factory, answer, add_run, capsys):
    for days_old in (31, 40, 400):  # three old runs: two batches of RETENTION_BATCH_SIZE=2
        add_run(1, days_old)
    recent = add_run(1, 29)
    answer([live(1, 30)])

    assert run_job(session_factory) == 0

    assert remaining(db) == [recent]
    assert db.query(RunResult).count() == 1
    assert summary(capsys) == {"event": "retention", "projects": 1, "runs_deleted": 3, "keys_revoked": 0,
                               "projects_skipped": 0, "dry_run": False}


def test_a_deleted_projects_runs_are_deleted_and_its_keys_revoked(db, session_factory, answer, add_run, make_key):
    add_run(2, 0)
    live_key, _ = make_key(project_id=2)
    old_revoked, _ = make_key(project_id=2, revoked=True)
    revoked_before = old_revoked.revoked_at
    answer([{"project_id": 2, "result_retention_days": 90, "deleted": True}])

    assert run_job(session_factory) == 0

    assert remaining(db) == []
    db.refresh(live_key)
    db.refresh(old_revoked)
    assert live_key.revoked_at is not None
    assert old_revoked.revoked_at == revoked_before


def test_projects_missing_from_the_list_are_never_touched(db, session_factory, answer, add_run, capsys):
    kept = add_run(3, 1000)
    answer([])

    assert run_job(session_factory) == 0

    assert remaining(db) == [kept]
    assert summary(capsys)["projects_skipped"] == 1


@pytest.mark.parametrize("reply", [
    {"exc": httpx.ConnectError("connection refused")},
    {"status_code": 401, "body": {"detail": "Invalid internal credentials"}},
    {"status_code": 500, "body": {"detail": "boom"}},
    {"text": "<html>maintenance</html>"},
    {"body": [1, 2]},
    {"body": {"projects": "all"}},
    {"body": {"projects": [{"project_id": "1", "result_retention_days": 30, "deleted": False}]}},
    {"body": {"projects": [{"project_id": True, "result_retention_days": 30, "deleted": False}]}},
    {"body": {"projects": [{"project_id": 1, "result_retention_days": 0, "deleted": False}]}},
    {"body": {"projects": [{"project_id": 1, "result_retention_days": 30, "deleted": "no"}]}},
])
def test_without_a_trustworthy_answer_nothing_is_deleted(db, session_factory, answer, add_run, capsys, reply):
    old = add_run(1, 400)
    answer(**reply)

    assert run_job(session_factory) == 1

    assert remaining(db) == [old]
    assert json.loads(capsys.readouterr().err.strip().splitlines()[-1])["event"] == "retention_failed"


def test_dry_run_reports_but_changes_nothing(db, session_factory, answer, add_run, capsys):
    old, recent, gone = add_run(1, 400), add_run(1, 1), add_run(2, 0)
    answer([live(1, 30), {"project_id": 2, "result_retention_days": 30, "deleted": True}])

    assert run_job(session_factory, "--dry-run") == 0

    assert remaining(db) == sorted([old, recent, gone])
    assert db.query(ApiKey).filter(ApiKey.revoked_at.isnot(None)).count() == 0
    reported = summary(capsys)
    assert (reported["runs_deleted"], reported["keys_revoked"], reported["dry_run"]) == (2, 1, True)


def test_the_request_carries_basic_credentials_and_no_userinfo(session_factory, answer):
    route = answer([])

    assert run_job(session_factory) == 0

    request = route.calls.last.request
    assert str(request.url) == RETENTION_URL
    expected = base64.b64encode(f"ingestion-service:{PASSWORD}".encode()).decode()
    assert request.headers["Authorization"] == f"Basic {expected}"


def test_the_password_never_appears_in_the_output(session_factory, answer, capsys):
    answer(status_code=401, body={"detail": "Invalid internal credentials"})
    assert run_job(session_factory) == 1
    answer([])
    assert run_job(session_factory) == 0

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert PASSWORD not in output and "p%40ss" not in output
    assert "http://ingestion-service:***@project-service:8000" in captured.err


@pytest.mark.parametrize("url", [
    "",
    "not a url",
    "http://project-service:8000",
    "http://ingestion-service@project-service:8000",
    "http://ingestion-service:@project-service:8000",
    "ftp://ingestion-service:pw@project-service:8000",
])
def test_an_unusable_connection_string_fails_the_pass(session_factory, monkeypatch, capsys, http, url):
    monkeypatch.setattr(settings, "PROJECT_SERVICE_INTERNAL_URL", url)

    assert run_job(session_factory) == 1

    assert "PROJECT_SERVICE_INTERNAL_URL" in capsys.readouterr().err
    assert not http.calls


def test_the_loop_survives_a_failed_pass_and_stops_when_asked(monkeypatch, session_factory):
    calls = []
    stop = threading.Event()

    def fake_run_once(**kwargs):
        calls.append(kwargs["dry_run"])
        if len(calls) == 3:
            stop.set()
        return len(calls) != 1  # the first pass fails

    monkeypatch.setattr(retention, "run_once", fake_run_once)
    monkeypatch.setattr(settings, "RETENTION_INTERVAL_HOURS", 0)

    assert retention.main(["--loop"], now=lambda: NOW, session_factory=session_factory, stop=stop) == 0
    assert calls == [False, False, False]
```

- [ ] **Step 2: Run the tests to see them fail**

Run (from `platforms/ingestion-service`): `SECRET_KEY=x $PY -m pytest tests/integration/test_retention_job.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'src.ingestion.jobs'`.

- [ ] **Step 3: Settings**

In `platforms/ingestion-service/src/ingestion/core/config.py`, add at the end of `Settings`:

```python
    # The retention job (src/ingestion/jobs/retention.py). project-service's internal API with
    # HTTP Basic credentials in the URL: http://user:password@host:port (percent-encode special
    # characters in the password)
    PROJECT_SERVICE_INTERNAL_URL: str = ""
    RETENTION_INTERVAL_HOURS: float = 24.0
    RETENTION_BATCH_SIZE: int = 500
```

- [ ] **Step 4: Write the job**

Create the empty `platforms/ingestion-service/src/ingestion/jobs/__init__.py`.

`platforms/ingestion-service/src/ingestion/jobs/retention.py`:

```python
"""Retention: delete runs older than each project's retention period, and empty deleted projects.

    python -m src.ingestion.jobs.retention [--dry-run] [--loop]

Retention periods come from project-service's internal endpoint, called with the HTTP Basic
credentials in PROJECT_SERVICE_INTERNAL_URL. A pass that cannot get a trustworthy answer deletes
nothing, and projects missing from the answer are never touched, so a bug or an empty list can
never wipe data.
"""
import argparse
import json
import signal
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator, List, Optional
from urllib.parse import unquote, urlsplit, urlunsplit

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Query, Session, sessionmaker

from src.ingestion.core.config import settings
from src.ingestion.models import ApiKey, Run, RunResult

RETENTION_PATH = "/internal/v1/projects/retention"
LOCK_ID = 7_351_001  # any fixed number; only this job takes it
TIMEOUT_SECONDS = 10.0


class RetentionError(Exception):
    """The pass cannot run safely, so it deletes nothing. Messages never contain the password."""


@dataclass(frozen=True)
class Policy:
    project_id: int
    days: int
    deleted: bool


@dataclass(frozen=True)
class Endpoint:
    url: str        # without credentials
    username: str
    password: str
    display: str    # for logs: the password replaced with ***


def parse_internal_url(value: str) -> Endpoint:
    problem = RetentionError("PROJECT_SERVICE_INTERNAL_URL must look like http://user:password@host:port")
    try:
        parts = urlsplit(value.strip())
        username, password, hostname = parts.username, parts.password, parts.hostname
    except ValueError:
        raise problem from None
    if parts.scheme not in ("http", "https") or not hostname or not username or not password:
        raise problem
    host = parts.netloc.rpartition("@")[2]
    path = parts.path.rstrip("/")
    return Endpoint(
        url=urlunsplit((parts.scheme, host, path + RETENTION_PATH, "", "")),
        username=unquote(username),
        password=unquote(password),
        display=urlunsplit((parts.scheme, f"{username}:***@{host}", path, "", "")),
    )


def fetch_policies(endpoint: Endpoint) -> List[Policy]:
    try:
        response = httpx.get(endpoint.url, auth=(endpoint.username, endpoint.password), timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise RetentionError(f"cannot reach {endpoint.display}: {type(exc).__name__}: {exc}") from None
    if response.status_code != 200:
        raise RetentionError(f"{endpoint.display} answered {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        raise RetentionError(f"{endpoint.display} returned a body that is not JSON") from None
    projects = body.get("projects") if isinstance(body, dict) else None
    if not isinstance(projects, list):
        raise RetentionError(f"{endpoint.display} returned an unexpected body")
    return [_policy(item, endpoint) for item in projects]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)  # bool is a subclass of int


def _policy(item: object, endpoint: Endpoint) -> Policy:
    if (
        not isinstance(item, dict)
        or not _is_int(item.get("project_id"))
        or not _is_int(item.get("result_retention_days"))
        or not 1 <= item["result_retention_days"] <= 365
        or not isinstance(item.get("deleted"), bool)
    ):
        raise RetentionError(f"{endpoint.display} returned an unexpected body")
    return Policy(project_id=item["project_id"], days=item["result_retention_days"], deleted=item["deleted"])


def run_pass(db: Session, policies: List[Policy], now: datetime, *, batch_size: int, dry_run: bool) -> dict:
    runs_deleted = keys_revoked = 0
    for policy in policies:
        runs = db.query(Run.id).filter(Run.project_id == policy.project_id)
        if not policy.deleted:
            runs = runs.filter(Run.created_at < now - timedelta(days=policy.days))
        runs_deleted += runs.count() if dry_run else _delete_in_batches(db, runs, batch_size)
        if policy.deleted:
            keys = db.query(ApiKey).filter(ApiKey.project_id == policy.project_id, ApiKey.revoked_at.is_(None))
            if dry_run:
                keys_revoked += keys.count()
            else:
                keys_revoked += keys.update({ApiKey.revoked_at: now}, synchronize_session=False)
                db.commit()
    listed = {policy.project_id for policy in policies}
    known = {pid for (pid,) in db.query(Run.project_id).distinct()} | {
        pid for (pid,) in db.query(ApiKey.project_id).distinct()
    }
    return {
        "event": "retention",
        "projects": len(policies),
        "runs_deleted": runs_deleted,
        "keys_revoked": keys_revoked,
        "projects_skipped": len(known - listed),
        "dry_run": dry_run,
    }


def _delete_in_batches(db: Session, runs: Query, batch_size: int) -> int:
    deleted = 0
    while True:
        batch = [run_id for (run_id,) in runs.order_by(Run.id).limit(batch_size)]
        if not batch:
            return deleted
        # Results first, explicitly: SQLite (the tests) does not enforce ON DELETE CASCADE by default
        db.query(RunResult).filter(RunResult.run_id.in_(batch)).delete(synchronize_session=False)
        db.query(Run).filter(Run.id.in_(batch)).delete(synchronize_session=False)
        db.commit()
        deleted += len(batch)


@contextmanager
def _advisory_lock(engine: Engine) -> Iterator[bool]:
    """One pass at a time across every copy of the job; PostgreSQL only (the tests use SQLite)."""
    if engine.dialect.name != "postgresql":
        yield True
        return
    with engine.connect() as conn:
        acquired = bool(conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}).scalar())
        conn.commit()
        try:
            yield acquired
        finally:
            if acquired:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
                conn.commit()


def _log(record: dict, error: bool = False) -> None:
    print(json.dumps(record), file=sys.stderr if error else sys.stdout, flush=True)


def run_once(*, dry_run: bool, now: Callable[[], datetime], session_factory: sessionmaker, lock_engine: Engine) -> bool:
    try:
        endpoint = parse_internal_url(settings.PROJECT_SERVICE_INTERNAL_URL)
        with _advisory_lock(lock_engine) as acquired:
            if not acquired:
                _log({"event": "retention_skipped", "reason": "another pass is already running"})
                return True
            policies = fetch_policies(endpoint)
            with session_factory() as db:
                summary = run_pass(db, policies, now(), batch_size=settings.RETENTION_BATCH_SIZE, dry_run=dry_run)
    except RetentionError as exc:
        _log({"event": "retention_failed", "error": str(exc)}, error=True)
        return False
    except Exception as exc:  # e.g. the database is down: report it; the loop tries again later
        _log({"event": "retention_failed", "error": f"{type(exc).__name__}: {exc}"}, error=True)
        return False
    _log(summary)
    return True


def main(
    argv: Optional[List[str]] = None,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    session_factory: Optional[sessionmaker] = None,
    lock_engine: Optional[Engine] = None,
    stop: Optional[threading.Event] = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.ingestion.jobs.retention",
        description="Delete runs older than each project's retention period; empty deleted projects.",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would be deleted; change nothing")
    parser.add_argument("--loop", action="store_true", help="a pass now, then every RETENTION_INTERVAL_HOURS")
    args = parser.parse_args(argv)

    if session_factory is None:
        from src.ingestion.db.session import SessionLocal

        session_factory = SessionLocal
    if lock_engine is None:
        lock_engine = session_factory.kw["bind"]

    def once() -> bool:
        return run_once(dry_run=args.dry_run, now=now, session_factory=session_factory, lock_engine=lock_engine)

    if not args.loop:
        return 0 if once() else 1

    if stop is None:
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
    while not stop.is_set():
        once()  # a failed pass is logged; the next one may succeed
        stop.wait(settings.RETENTION_INTERVAL_HOURS * 3600)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git status --short
git add platforms/ingestion-service/src/ingestion/jobs platforms/ingestion-service/src/ingestion/core/config.py platforms/ingestion-service/tests/integration/test_retention_job.py
git commit -m "feat(ingestion): retention job deletes runs past each project's retention period

python -m src.ingestion.jobs.retention [--dry-run] [--loop]: gets every
project's period from project-service's internal endpoint (HTTP Basic
from a connection string), deletes old runs in batches, empties deleted
projects and revokes their keys, never touches projects missing from the
answer, and deletes nothing without a trustworthy answer. One pass at a
time via a PostgreSQL advisory lock; the password is never logged.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Stack, CI and smoke checks

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.github/workflows/ci.yml` (gateway job env)
- Modify: `scripts/smoke_gateway.sh`
- Modify: `README.md` (root quick start)

**Interfaces:**
- Consumes: Task 3's endpoint and settings; Task 4's command and settings; Task 2's masking (read back through the gateway).
- Produces: compose service `ingestion-retention`; required variable `INTERNAL_API_PASSWORD` for every root `docker compose` command and for the smoke script.

- [ ] **Step 1: Compose**

In `docker-compose.yml`:

In `x-project-env`, after `ORGANIZATION_SERVICE_URL: http://organization-service:8000`, add:

```yaml
  # Internal API (GET /internal/v1/projects/retention), used by ingestion-retention
  INTERNAL_API_PASSWORD: ${INTERNAL_API_PASSWORD:?set INTERNAL_API_PASSWORD (project-service's internal API; URL-safe characters)}
```

After the `ingestion-service:` service block (before `gateway:`), add:

```yaml
  # Deletes runs past each project's retention period: a pass at start-up, then every
  # RETENTION_INTERVAL_HOURS. One pass at a time across copies (PostgreSQL advisory lock).
  ingestion-retention:
    # Same image as ingestion-service, which builds it; never pulled from a registry
    image: qa-vision/ingestion-service:local
    pull_policy: never
    environment:
      <<: *ingestion-env
      # HTTP Basic credentials as a connection string; the password must be URL-safe here
      PROJECT_SERVICE_INTERNAL_URL: http://ingestion-service:${INTERNAL_API_PASSWORD:?set INTERNAL_API_PASSWORD (project-service's internal API; URL-safe characters)}@project-service:8000
    command: ["python", "-m", "src.ingestion.jobs.retention", "--loop"]
    depends_on:
      ingestion-migrate:
        condition: service_completed_successfully
      project-service:
        condition: service_healthy
```

In the `gateway` service's `depends_on`, after the `ingestion-service:` entry, add:

```yaml
      # Not needed by the gateway; listed so `docker compose up gateway` starts the whole platform
      ingestion-retention:
        condition: service_started
```

Update the first comment line of the file to: `# The whole platform on one host: `SECRET_KEY=... INTERNAL_API_PASSWORD=... docker compose up -d --build --wait gateway`.`

Run: `SECRET_KEY=x INTERNAL_API_PASSWORD=y docker compose config --quiet && echo ok`
Expected: `ok`. And `SECRET_KEY=x docker compose config --quiet` fails with `set INTERNAL_API_PASSWORD`.

- [ ] **Step 2: CI**

In `.github/workflows/ci.yml`, in the `gateway` job's `env:`, after `SECRET_KEY: ci-gateway-secret`, add:

```yaml
      # Required by docker-compose.yml as well (project-service's internal API)
      INTERNAL_API_PASSWORD: ci-internal-secret
```

- [ ] **Step 3: Smoke script**

In `scripts/smoke_gateway.sh`:

Replace the `SECRET_KEY` check block

```bash
if [ -z "${SECRET_KEY:-}" ]; then
  echo "FAIL  SECRET_KEY is not set: export the same value the stack was started with"
  exit 1
fi
```

with

```bash
for var in SECRET_KEY INTERNAL_API_PASSWORD; do
  if [ -z "${!var:-}" ]; then
    echo "FAIL  $var is not set: export the same value the stack was started with"
    exit 1
  fi
done
```

and update line 3's comment to `# Run from anywhere after:  SECRET_KEY=... INTERNAL_API_PASSWORD=... docker compose up -d --build --wait gateway`.

After the `body_has()` function, add:

```bash
# body_lacks NAME TEXT -- the last response body does not contain TEXT
body_lacks() {
  if grep -qF -- "$2" "$TMP/body" 2>/dev/null; then
    fail "$1: the body contains it"
  else
    pass "$1"
  fi
}
```

Immediately before `check "revoke the key" ...` (the key must still be valid), add:

```bash
# ---- masking: secrets in test output never reach the database ----
FAKE_TOKEN="ghp_"'SmokeSmokeSmokeSmokeSmokeSmokeSmoke0'  # token-shaped, not a real token
MASK_BODY="{\"run\":{\"ci_provider\":\"local\",\"branch\":\"smoke-mask\",\"started_at\":\"$NOW\",\"finished_at\":\"$NOW\"},\"results\":[{\"name\":\"leaks\",\"status\":\"failed\",\"message\":\"login as ann@acme.test\",\"details\":\"GITHUB_TOKEN=$FAKE_TOKEN\"}]}"
check "upload a run whose output contains a token" 201 POST "$BASE/api/v1/collect/runs" \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" -d "$MASK_BODY"
MASK_RUN_ID="$(grep -o '"id":[0-9]*' "$TMP/body" | head -1 | cut -d: -f2)"
check "read the masked run" 200 GET "$BASE/api/v1/runs/${MASK_RUN_ID:-0}" "${AUTH[@]}"
body_has "... the token is masked" '[REDACTED:github_token]'
body_has "... the email is masked" '[REDACTED:email]'
body_has "... and the result is flagged" '"redacted":true'
body_lacks "... the token itself is not stored" "$FAKE_TOKEN"

```

After `check "/metrics is not exposed through the gateway" 404 GET "$BASE/metrics"`, add:

```bash
check "/internal is not exposed through the gateway" 404 GET "$BASE/internal/v1/projects/retention"

# ---- retention: the job runs, and really reaches project-service inside the stack ----
if docker compose ps --status running --services 2>/dev/null | grep -qx ingestion-retention; then
  pass "ingestion-retention is running"
else
  fail "ingestion-retention is not running"
fi
if docker compose run --rm -T ingestion-retention python -m src.ingestion.jobs.retention --dry-run \
     >"$TMP/retention_out" 2>"$TMP/retention_err"; then
  if grep -q '"event": "retention"' "$TMP/retention_out"; then
    pass "retention job dry run inside the stack"
  else
    fail "retention job dry run printed no summary: $(tail -c 300 "$TMP/retention_out")"
  fi
else
  fail "retention job dry run: $(tail -c 400 "$TMP/retention_err")"
fi
if grep -qF -- "$INTERNAL_API_PASSWORD" "$TMP/retention_out" "$TMP/retention_err"; then
  fail "retention job output contains the internal password"
else
  pass "retention job output never shows the internal password"
fi
```

Run: `bash -n scripts/smoke_gateway.sh && echo syntax-ok`
Expected: `syntax-ok`.

- [ ] **Step 4: Root README**

In `README.md`, after the line `export SECRET_KEY=<a long random value>        # required by EVERY docker compose command here`, add:

```bash
export INTERNAL_API_PASSWORD=<a long random value, URL-safe, e.g. openssl rand -hex 32>   # required too
```

- [ ] **Step 5: Run the stack and the smoke test**

Run (repository root, Git Bash; port 8080 is taken on this machine):

```bash
export SECRET_KEY=local-smoke-secret INTERNAL_API_PASSWORD=local-internal-secret GATEWAY_HTTP_PORT=18080
docker compose up -d --build --wait --wait-timeout 300 gateway
bash scripts/smoke_gateway.sh
docker compose logs ingestion-retention | tail -5
```

Expected: every smoke line starts with `ok`, including the masking checks, `/internal is not exposed through the gateway (404)`, `ingestion-retention is running`, `retention job dry run inside the stack`, and `retention job output never shows the internal password`; last line `all gateway checks passed`. The retention logs show a `{"event": "retention", ...}` line from its start-up pass.

Then stop the stack, keeping the data volume: `docker compose down`.

- [ ] **Step 6: Commit**

```bash
git status --short
git add docker-compose.yml .github/workflows/ci.yml scripts/smoke_gateway.sh README.md
git commit -m "feat: retention job in the stack; smoke checks for masking and /internal

INTERNAL_API_PASSWORD is now required (project-service's internal API);
ingestion-retention runs the job in a loop and starts with the platform.
The smoke test checks that a token in test output is masked when read
back, that /internal is not reachable through the gateway, and that a
real dry-run pass reaches project-service without logging the password.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Documentation and TODO

**Files:**
- Modify: `platforms/ingestion-service/README.md`
- Modify: `TODO.md`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: documentation only.

- [ ] **Step 1: ingestion-service README**

In `platforms/ingestion-service/README.md`, insert before the `## Operations` heading:

```markdown
## Masking

Before a result is stored, its `message` and `details` are masked, and so is a password inside
the run's `ci_run_url`. Each masked value becomes `[REDACTED:<kind>]`; the text around it stays
readable. Test names, suites, classes, files and branches are never changed.

| Kind | Matches |
|---|---|
| `private_key` | `-----BEGIN … PRIVATE KEY-----` blocks (to the end of the text if unterminated) |
| `authorization` | the value of an `Authorization` / `Proxy-Authorization` header (the scheme word is kept) |
| `url_password` | the password in `scheme://user:password@` |
| `jwt` | JSON Web Tokens |
| `github_token`, `gitlab_token`, `aws_access_key`, `slack_token`, `stripe_key`, `google_api_key`, `npm_token`, `qav_key` | well-known token formats |
| `password`, `secret`, `token`, `api_key`, `access_key`, `client_secret`, `private_key`, `credentials` | the value in `key=value`, `key: value` or `"key": "value"` when the key ends with one of these names (`DB_PASSWORD`, `X-Api-Key`, `accessToken`, …) |
| `email` | email addresses |
| `card_number` | 13–19 digit card numbers with a card prefix that pass the Luhn check |

- Masking happens before the 64 KB cut, so a secret on the boundary is never half-stored.
- Each result has a `redacted` flag; `qav_ingest_redactions_total{kind}` counts results by kind.
- Results stored before masking existed are not re-masked.

## Retention

`python -m src.ingestion.jobs.retention [--dry-run] [--loop]` (the `ingestion-retention` compose
service runs it with `--loop`):

- Gets every project's `result_retention_days` from project-service's
  `GET /internal/v1/projects/retention`, with the HTTP Basic credentials in
  `PROJECT_SERVICE_INTERNAL_URL` (`http://ingestion-service:<password>@project-service:8000`;
  percent-encode special characters).
- Deletes runs uploaded (`created_at`) more than that many days ago; deletes all runs of deleted
  projects and revokes their API keys.
- Without a trustworthy answer (unreachable, not 200, unexpected body) it deletes nothing and
  exits 1. Projects missing from the answer are never touched.
- `RETENTION_INTERVAL_HOURS` (default 24) between passes with `--loop`; `RETENTION_BATCH_SIZE`
  (default 500) runs per transaction. One pass at a time (PostgreSQL advisory lock).
- Logs one JSON line per pass; the password is never logged (`user:***@host`).

```

- [ ] **Step 2: TODO.md**

In `TODO.md`, replace

```
- [ ] PII detection and redaction; retention policies
```

with

```
- [x] PII detection and redaction; retention policies — masking on ingest, `ingestion-retention` job
```

and replace

```
- [ ] Revoke a project's API keys when the project is deleted
```

with

```
- [x] Revoke a project's API keys when the project is deleted — done by the retention job
- [ ] Re-mask results stored before masking existed (one-off command)
- [ ] Custom masking patterns per project
- [ ] Legal hold and data export before deletion
```

- [ ] **Step 3: Check and commit**

Run: `grep -n "Masking\|Retention" platforms/ingestion-service/README.md && grep -n "retention job\|Re-mask" TODO.md`
Expected: the two new README headings and the TODO lines.

```bash
git status --short
git add platforms/ingestion-service/README.md TODO.md
git commit -m "docs(ingestion): masking and retention; TODO

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
