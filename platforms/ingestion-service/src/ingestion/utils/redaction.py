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


_BEGIN_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY(?: BLOCK)?-----")
_END_PRIVATE_KEY = re.compile(r"-----END [A-Z0-9 ]{0,40}PRIVATE KEY(?: BLOCK)?-----")

# Scheme words kept in front of a masked credential
_SCHEMES = r"(?:bearer|basic|token|digest|negotiate|ntlm)"

# The value of an Authorization header, to the end of the line or the closing quote (a value such as
# "AWS4-HMAC-SHA256 Credential=..., Signature=..." has spaces); a known scheme word is kept
_AUTHORIZATION = re.compile(
    r"(?i)\b((?:proxy-)?authorization[\"']?[ \t]{0,5}[:=][ \t]{0,5}[\"']?"
    r"(?:" + _SCHEMES + r"[ \t]{1,5})?)"
    r"([^\r\n\"']{1,4096})"
)

# Cookie / Set-Cookie header values: session identifiers, to the end of the line
_COOKIE = re.compile(r"(?i)(?<![A-Za-z0-9_\-])((?:set-)?cookie[ \t]{0,5}:[ \t]{0,5})([^\r\n]{1,4096})")

# scheme://user:password@ -- the user name (possibly empty: redis://:pw@host) is kept
_URL_PASSWORD = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]{0,20}://[^\s:/@\"'<>]{0,256}:)([^\s/@\"'<>]{1,256})(@)")

# curl -u user:password / --user user:password, and --password secret (a space instead of "=")
_CLI_USER = re.compile(r"(?<![A-Za-z0-9_\-])((?:-u|--user)[ \t]{1,5}[^\s:\"']{1,256}:)([^\s\"']{1,4096})")
_CLI_PASSWORD = re.compile(r"(?<![A-Za-z0-9_\-])(--(?:password|passwd|pass)[ \t]{1,5})((?!-)[^\s\"']{1,4096})")

# <password>value</password>, for any tag _secret_kind recognises
_XML_ELEMENT = re.compile(r"<([A-Za-z_][A-Za-z0-9_.:\-]{0,63})>([^<]{1,4096})</\1>")

_JWT = re.compile(r"\beyJ[A-Za-z0-9_\-]{5,4096}\.eyJ[A-Za-z0-9_\-]{5,8192}\.[A-Za-z0-9_\-]{0,4096}")

_TOKENS = (
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255})\b")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,255}")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,255}")),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,255}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}(?![0-9A-Za-z_\-])")),
    ("npm_token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    # Project API keys: `qeos_…`, and `qav_…` issued before the QEOS rename. The kind keeps its
    # pre-rename name, so markers already stored ([REDACTED:qav_key]) and the redactions metric's
    # label stay the same; it is kept for compatibility, not an oversight.
    ("qav_key", re.compile(r"\b(?:qeos|qav)_[A-Za-z0-9_\-]{43}(?![A-Za-z0-9_\-])")),
)

# key=value, key: value, "key": "value", 'key': 'value'. The key is matched as a whole word and
# checked against _SECRET_NAMES in Python; only then is the value matched, so text full of
# non-secret pairs costs one short match each, never a scan of every value.
# Separators: = : => := (and a backslash before the key's closing quote, for JSON escaped in a log)
_KEY_SEPARATOR = re.compile(
    r"(?<![A-Za-z0-9_.\-])([A-Za-z0-9_.\-]{1,64})\\?[\"']?[ \t]{0,5}(?:=>|:=|[:=])[ \t]{0,5}"
)
# A value: \"escaped\", "double-quoted", 'single-quoted', or unquoted. A known scheme word in front
# (token: Bearer abc) is kept and the credential after it masked. An unquoted value ends at
# whitespace or a quote; ; , & end it only when another key=value follows (Server=db;Password=a;b;Database=x)
_VALUE = re.compile(
    r"(?i:" + _SCHEMES + r"[ \t]{1,5})?"
    r"(?:\\\"([^\"\\\r\n]{1,4096})\\\"|\"([^\"\r\n]{1,4096})\"|'([^'\r\n]{1,4096})'"
    r"|((?:[^\s\"';,&=]|[;,&](?![ \t]{0,5}[A-Za-z_][A-Za-z0-9_.\-]{0,63}[ \t]{0,5}=)){1,4096}))"
)
# (normalised key suffix, kind); longest first, so client_secret wins over secret
_SECRET_NAMES = (
    ("encryptionkey", "secret"),
    ("clientsecret", "client_secret"),
    ("credentials", "credentials"),
    ("privatekey", "private_key"),
    ("signingkey", "secret"),
    ("secretkey", "secret"),
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
    text = _COOKIE.sub(lambda m: _mask_group(m, 2, "cookie", found), text)
    text = _URL_PASSWORD.sub(lambda m: _mask_group(m, 2, "url_password", found), text)
    text = _CLI_USER.sub(lambda m: _mask_group(m, 2, "password", found), text)
    text = _CLI_PASSWORD.sub(lambda m: _mask_group(m, 2, "password", found), text)
    text = _mask_all(_JWT, "jwt", text, found)
    for kind, pattern in _TOKENS:
        text = _mask_all(pattern, kind, text, found)
    text = _XML_ELEMENT.sub(lambda m: _mask_element(m, found), text)
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
        key = _KEY_SEPARATOR.search(text, pos)
        if key is None:
            break
        # The search goes on right after the separator either way: a value that is not a secret
        # can still hold one (opts=--password=x)
        pos = key.end()
        kind = _secret_kind(key.group(1))
        if kind is None:
            continue
        value = _VALUE.match(text, key.end())
        if value is None:
            continue
        group = next(g for g in (1, 2, 3, 4) if value.group(g) is not None)
        if value.group(group).startswith(MARKER_PREFIX):
            continue
        found.add(kind)
        start, end = value.span(group)  # the value only; quotes around it stay
        pieces.append(text[last:start])
        pieces.append(marker(kind))
        last = pos = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mask_element(match: "re.Match[str]", found: Set[str]) -> str:
    kind = _secret_kind(match.group(1))
    if kind is None:
        return match.group(0)
    return _mask_group(match, 2, kind, found)


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
