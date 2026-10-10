"""Heartbeat error texts: one line, at most 500 characters, no secrets (spec §3, Review Focus 2)."""
import pytest

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
    out = short_error("cannot connect: host=db password=hunter2 user=x")
    assert "hunter2" not in out and out.startswith("cannot connect: host=db password=") and out.endswith(" user=x")


def test_an_empty_error_is_an_empty_string():
    assert short_error("") == ""


@pytest.mark.parametrize("text,secret", [
    ("conn postgresql://u:pw123@db:5432/x failed", "pw123"),
    ("conn postgres://u:pw123@db/x failed", "pw123"),
    ("conn mysql://u:pw123@db/x failed", "pw123"),
    ("conn redis://:pw123@cache:6379/0 failed", "pw123"),
    ("conn postgresql://u:pa/ss123@db/x failed", "ss123"),
    ("conn postgresql://u:p@ss123@db/x failed", "ss123"),
    ("conn postgresql://u:p@ss123@db/x failed", "p@ss"),
    ("db_password=pw123 refused", "pw123"),
    ("PGPASSWORD=pw123 refused", "pw123"),
    ("password='pw123 and more' refused", "pw123"),
    ('password="pw123 and more" refused', "more"),
    ("password: pw123 refused", "pw123"),
    ("passwd=pw123 refused", "pw123"),
    ("api token=pw123 refused", "pw123"),
    ('failed {"password": "s3cret"}', "s3cret"),
    ("failed {'password': 's3cret'}", "s3cret"),
    ("failed Authorization: Bearer s3crettoken123", "s3crettoken123"),
    ("failed Bearer s3crettoken123", "s3crettoken123"),
    ("failed api_key=s3cret", "s3cret"),
    ("failed apikey: s3cret", "s3cret"),
    ("failed SECRET_KEY=s3cret", "s3cret"),
    ("failed passphrase=s3cret", "s3cret"),
    ('failed passphrase: "s3 cret"', "cret"),
])
def test_no_secret_survives(text, secret):
    assert secret not in short_error(text)


def test_a_user_only_url_keeps_its_host():
    assert short_error("conn postgresql://user@db:5432/x failed") == "conn postgresql://***@db:5432/x failed"


def test_a_multi_line_traceback_is_one_line_without_the_secret():
    out = short_error("OperationalError: postgresql://u:pw123@db/x\nTraceback:\n  password=pw123")
    assert out == "OperationalError: postgresql://***@db/x"


@pytest.mark.parametrize("secret", ["pw123XYZ456", "p@ss/w0rd!!"])
def test_a_secret_straddling_character_500_leaves_no_part(secret):
    for offset in (488, 494, 500, 506):
        text = "x" * (offset - len(" password=")) + " password=" + secret + " tail"
        out = short_error(text)
        assert len(out) <= MAX_ERROR
        assert secret[:4] not in out and secret not in out
    text = "x" * 480 + " postgresql://u:" + secret + "@db/x tail"
    out = short_error(text)
    assert secret[:4] not in out and len(out) <= MAX_ERROR
