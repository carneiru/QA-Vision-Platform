import hashlib
import re

from src.ingestion.utils.keys import PREFIX, display_prefix, generate_key, hash_key


def test_keys_have_the_prefix_and_256_bits():
    key = generate_key()
    assert key.startswith(PREFIX)
    assert re.fullmatch(r"qav_[A-Za-z0-9_-]{43}", key)


def test_keys_are_unique():
    assert len({generate_key() for _ in range(100)}) == 100


def test_hash_is_sha256_hex_of_the_whole_key():
    key = generate_key()
    assert hash_key(key) == hashlib.sha256(key.encode()).hexdigest()


def test_display_prefix_is_the_first_12_characters():
    key = generate_key()
    assert display_prefix(key) == key[:12]
    assert len(display_prefix(key)) == 12
