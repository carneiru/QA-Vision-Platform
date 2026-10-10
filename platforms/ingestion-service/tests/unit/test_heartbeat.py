"""Heartbeat error texts: one line, at most 500 characters, no secrets (spec §3, Review Focus 2)."""
from src.ingestion.jobs.heartbeat import MAX_ERROR, short_error


def test_only_the_first_line_is_kept():
    assert short_error("RuntimeError: boom\nTraceback (most recent call last):\n  File x") == "RuntimeError: boom"


def test_the_text_is_cut_at_500_characters():
    assert len(short_error("x" * 2000)) == MAX_ERROR == 500


def test_credentials_in_a_url_are_replaced():
    text = short_error('OperationalError: connection to "postgresql://postgres:s3cr%40t@postgres:5432/ingestion_db" failed')
    assert "s3cr" not in text and "postgres:s3cr" not in text
    assert "postgresql://***@postgres:5432/ingestion_db" in text


def test_a_password_pair_is_replaced():
    assert short_error("cannot connect: host=db password=hunter2 user=x") == "cannot connect: host=db password=*** user=x"


def test_an_empty_error_is_an_empty_string():
    assert short_error("") == ""
