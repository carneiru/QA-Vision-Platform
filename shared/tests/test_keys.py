import hashlib

from qeos_shared.keys import test_key as make_test_key


def test_key_is_sha256_of_the_three_parts_joined_by_nul():
    expected = hashlib.sha256("checkout\0CartTest\0adds item".encode("utf-8")).hexdigest()
    assert make_test_key("checkout", "CartTest", "adds item") == expected


def test_nul_separator_keeps_shifted_parts_apart():
    assert make_test_key("a", "bc", "d") != make_test_key("ab", "c", "d")
