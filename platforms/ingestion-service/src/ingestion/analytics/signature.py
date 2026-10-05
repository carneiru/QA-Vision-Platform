"""Failure signatures: which failed tests share one cause.

The first line of an error message names the cause ("TimeoutError: … locator('#pay-button')").
Values that change from run to run — durations, line numbers, ids, hashes — are replaced with
placeholders; everything else, quoted locators included, stays, so a different locator is a
different cause. Messages are already masked when stored, so signatures never see secrets.
"""
import hashlib
import re
from typing import Optional

MAX_LINE = 500  # only the start of a line names the cause; also bounds the regex work
HEADLINE = 300
NONE = "none"   # the shared signature of failures without a message

_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_HEX_PREFIXED = re.compile(r"\b0[xX][0-9a-fA-F]+\b")
# Commit shas, object ids, addresses: 7+ hex characters with at least one digit, so plain
# words made of a-f letters ("defaced") survive
_HEX = re.compile(r"\b(?=[0-9a-fA-F]*\d)[0-9a-fA-F]{7,}\b")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_SPACE = re.compile(r"\s+")


def headline(message: Optional[str]) -> Optional[str]:
    """The first non-empty line, trimmed: what people read as the error."""
    for line in (message or "").splitlines():
        line = line.strip()
        if line:
            return line[:HEADLINE]
    return None


def normalize(message: Optional[str]) -> str:
    line = (headline(message) or "")[:MAX_LINE]
    line = _UUID.sub("<id>", line)
    line = _HEX_PREFIXED.sub("<hex>", line)
    line = _HEX.sub("<hex>", line)
    line = _NUMBER.sub("<n>", line)
    return _SPACE.sub(" ", line).strip()


def signature(message: Optional[str]) -> str:
    text = normalize(message)
    if not text:
        return NONE
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
