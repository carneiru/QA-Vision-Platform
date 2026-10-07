import hashlib
import re

from src.ingestion.utils.keys import LEGACY_PREFIX, PREFIX, display_prefix, generate_key, hash_key, is_api_key


def test_keys_have_the_prefix_and_256_bits():
    key = generate_key()
    assert PREFIX == "qeos_"
    assert key.startswith("qeos_")
    assert re.fullmatch(r"qeos_[A-Za-z0-9_-]{43}", key)


def test_keys_are_unique():
    assert len({generate_key() for _ in range(100)}) == 100


def test_hash_is_sha256_hex_of_the_whole_key():
    key = generate_key()
    assert hash_key(key) == hashlib.sha256(key.encode()).hexdigest()


def test_display_prefix_is_the_prefix_and_8_characters():
    key = generate_key()
    assert display_prefix(key) == key[:13]
    assert len(display_prefix(key)) == 13


def test_display_prefix_of_a_legacy_key_is_12_characters():
    key = LEGACY_PREFIX + "x" * 43
    assert display_prefix(key) == key[:12]


def test_both_prefixes_are_api_keys():
    assert LEGACY_PREFIX == "qav_"
    assert is_api_key("qeos_" + "a" * 43)
    assert is_api_key("qav_" + "a" * 43)  # issued before the QEOS rename; keeps working
    assert not is_api_key("not-a-key")
    assert not is_api_key("")
