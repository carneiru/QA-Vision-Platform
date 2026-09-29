import hashlib

from src.ingestion.service.ingest_service import test_key as make_test_key
from src.ingestion.service.ingest_service import truncate_utf8


def test_short_text_is_untouched():
    assert truncate_utf8("hello", 10) == ("hello", False)


def test_long_text_is_cut_to_the_byte_limit():
    text, cut = truncate_utf8("x" * 100, 10)
    assert (text, cut) == ("x" * 10, True)


def test_truncation_never_splits_a_character():
    # each 😀 is 4 bytes; a 10-byte limit fits two, and must not keep half of the third
    text, cut = truncate_utf8("😀😀😀", 10)
    assert cut is True
    assert text == "😀😀"
    text.encode("utf-8")  # valid UTF-8


def test_none_stays_none():
    assert truncate_utf8(None, 10) == (None, False)


def test_test_key_is_sha256_of_the_three_parts():
    expected = hashlib.sha256("checkout\0CartTest\0adds item".encode()).hexdigest()
    assert make_test_key("checkout", "CartTest", "adds item") == expected


def test_test_key_separator_prevents_collisions():
    assert make_test_key("a", "bc", "d") != make_test_key("ab", "c", "d")
