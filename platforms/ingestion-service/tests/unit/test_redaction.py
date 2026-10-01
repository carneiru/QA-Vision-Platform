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
], ids=lambda hostile: hostile[:12])  # short ids: pytest puts the id in an env var, capped on Windows
def test_hostile_input_is_fast(hostile):
    start = time.perf_counter()
    redact(hostile)
    assert time.perf_counter() - start < 1.0
