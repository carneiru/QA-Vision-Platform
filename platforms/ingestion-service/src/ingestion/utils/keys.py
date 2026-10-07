"""Project API keys: `qeos_` + 32 random bytes (URL-safe base64, 43 characters).

Keys issued before the QEOS rename start with `qav_`; they keep authenticating, so both
prefixes are accepted wherever a key is checked.

Stored as a SHA-256 hash. A 256-bit random key cannot be guessed, so a slow password hash
(bcrypt) buys nothing, and a fast hash allows the indexed lookup every upload needs.
"""
import hashlib
import secrets

PREFIX = "qeos_"
LEGACY_PREFIX = "qav_"
PREFIXES = (PREFIX, LEGACY_PREFIX)
# Characters after the prefix kept for listings
_DISPLAY_CHARS = 8


def generate_key() -> str:
    return PREFIX + secrets.token_urlsafe(32)


def is_api_key(value: str) -> bool:
    return value.startswith(PREFIXES)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def display_prefix(key: str) -> str:
    prefix = next((p for p in PREFIXES if key.startswith(p)), "")
    return key[: len(prefix) + _DISPLAY_CHARS] if prefix else key[:12]
