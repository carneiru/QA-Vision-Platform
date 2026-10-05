"""Failure signatures: one cause, one signature, whatever the run-specific values."""
import time

import pytest

from src.ingestion.analytics.signature import headline, normalize, signature


def test_numbers_ids_and_hashes_do_not_split_a_cause():
    a = "TimeoutError: Timeout 30000ms exceeded waiting for locator('#pay-button') at cart.spec.ts:88:12"
    b = "TimeoutError: Timeout 15000ms exceeded waiting for locator('#pay-button') at cart.spec.ts:112:5"
    assert signature(a) == signature(b)
    assert signature("order 3f2a9c1deadbeef not found") == signature("order 0a1b2c3d4e5f not found")
    assert signature("user 123e4567-e89b-12d3-a456-426614174000 missing") == signature(
        "user 00000000-0000-4000-8000-000000000001 missing")
    assert signature("AssertionError: 41.99 != 42.00") == signature("AssertionError: 7 != 8")


def test_a_different_locator_or_error_is_a_different_cause():
    assert signature("waiting for locator('#pay-button')") != signature("waiting for locator('#cart-total')")
    assert signature("TimeoutError: x") != signature("AssertionError: x")


def test_only_the_first_line_counts_and_whitespace_does_not():
    assert signature("AssertionError: expected 200\n  at foo (a.js:1)") == signature("AssertionError:  expected 500  \n  at bar")


def test_masked_values_group_together():
    assert signature("token [REDACTED:github_token] rejected") == signature("token [REDACTED:github_token] rejected")


def test_empty_messages_share_the_none_signature():
    assert signature(None) == signature("") == signature("   \n  ") == "none"


def test_signature_is_short_and_stable():
    s = signature("AssertionError: boom")
    assert len(s) == 12 and s == signature("AssertionError: boom")


def test_normalize_shows_what_was_replaced():
    assert normalize("Timeout 30000ms at 0x7ffd5e8 line 42") == "Timeout <n>ms at <hex> line <n>"


def test_headline_is_the_first_non_empty_line_trimmed():
    assert headline("\n\n  Error: boom  \n trace") == "Error: boom"
    assert headline(None) is None
    assert len(headline("x" * 1000)) == 300


@pytest.mark.parametrize("text", ["a" * 100_000, "1" * 100_000, ("ab12" * 25_000)], ids=["letters", "digits", "hexish"])
def test_long_inputs_stay_fast(text):
    started = time.perf_counter()
    signature(text)
    assert time.perf_counter() - started < 0.5
