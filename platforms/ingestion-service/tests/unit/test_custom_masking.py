import pytest

from src.ingestion.utils import custom_masking
from src.ingestion.utils.redaction import marker


def compiled(name, pattern):
    return custom_masking.CustomPattern(name=name, regex=custom_masking.compile_pattern(pattern))


def test_matches_become_named_markers():
    text, found = custom_masking.apply("order CUST-123456 for CUST-654321", [compiled("customer_id", r"CUST-\d{6}")])
    assert text == f"order {marker('customer_id')} for {marker('customer_id')}"
    assert found == {"customer_id"}


def test_existing_markers_are_never_rewritten():
    # A pattern that matches marker text must not mangle what built-in masking already did
    text, found = custom_masking.apply(f"x {marker('password')} REDACTED y", [compiled("word", r"REDACTED")])
    assert text == f"x {marker('password')} {marker('word')} y"


def test_no_patterns_or_no_text_is_a_no_op():
    assert custom_masking.apply("abc", []) == ("abc", set())
    assert custom_masking.apply("", [compiled("a", "a")]) == ("", set())


@pytest.mark.parametrize("pattern, reason", [
    (r"(unclosed", "not a valid pattern"),
    (r"(a)\1", "not a valid pattern"),      # backreferences: RE2 guarantees linear time by not having them
    (r"x*", "matches empty text"),
    (r"a|", "matches empty text"),
    ("a" * 257, "at most 256 characters"),
    ("", "required"),
])
def test_unsafe_or_useless_patterns_are_refused_with_a_reason(pattern, reason):
    with pytest.raises(ValueError, match=reason):
        custom_masking.compile_pattern(pattern)


def test_catastrophic_backtracking_input_finishes_fast():
    # (a+)+$ ruins a backtracking engine on "aaaa…b"; RE2 runs in linear time
    import time

    pattern = compiled("evil", r"(a+)+$")
    start = time.perf_counter()
    custom_masking.apply("a" * 50_000 + "b", [pattern])
    assert time.perf_counter() - start < 1.0


@pytest.mark.parametrize("name", ["customer_id", "a", "ticket2"])
def test_valid_names(name):
    assert custom_masking.validate_name(name) == name


@pytest.mark.parametrize("name", ["", "Customer", "1abc", "with space", "a" * 33, "dash-ed"])
def test_invalid_names(name):
    with pytest.raises(ValueError):
        custom_masking.validate_name(name)
