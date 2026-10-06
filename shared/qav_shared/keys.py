"""Identities shared by more than one service. Changing a formula here breaks every stored key."""
import hashlib


def test_key(suite: str, class_name: str, name: str) -> str:
    """Stable identity of a test across runs; the NUL separator keeps ("a","bc") and ("ab","c") apart.

    ingestion stores it on every result; test-management computes it for imported Gherkin
    scenarios so a case links to its automated results without a lookup (ADR-023)."""
    return hashlib.sha256(f"{suite}\0{class_name}\0{name}".encode("utf-8")).hexdigest()


test_key.__test__ = False  # not a pytest test, despite the name
