"""Project API keys: `qav_` + 32 random bytes (URL-safe base64, 43 characters).

Stored as a SHA-256 hash. A 256-bit random key cannot be guessed, so a slow password hash
(bcrypt) buys nothing, and a fast hash allows the indexed lookup every upload needs.
"""
import hashlib
import secrets

PREFIX = "qav_"


def generate_key() -> str:
    return PREFIX + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def display_prefix(key: str) -> str:
    return key[:12]
