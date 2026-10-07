"""The GitHub token at rest: Fernet with TM_SECRETS_KEY."""
import pytest
from cryptography.fernet import Fernet

from src.casebook.core.config import settings
from src.casebook.utils import secret_box

TOKEN = "github_pat_" + "a" * 40


def test_round_trip_and_the_ciphertext_hides_the_token(secrets_key):
    sealed = secret_box.encrypt(TOKEN)
    assert TOKEN not in sealed and secret_box.decrypt(sealed) == TOKEN
    assert secret_box.is_available()


def test_without_a_key_nothing_can_be_sealed(no_secrets_key):
    assert not secret_box.is_available()
    with pytest.raises(secret_box.SecretsUnavailable) as err:
        secret_box.encrypt(TOKEN)
    assert str(err.value) == "Running tests from QA Vision is not configured on this server"


def test_a_malformed_key_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "TM_SECRETS_KEY", "not-a-fernet-key")
    assert not secret_box.is_available()


def test_a_token_sealed_with_another_key_cannot_be_read(secrets_key, monkeypatch):
    sealed = secret_box.encrypt(TOKEN)
    monkeypatch.setattr(settings, "TM_SECRETS_KEY", Fernet.generate_key().decode())
    with pytest.raises(secret_box.SecretsUnavailable) as err:
        secret_box.decrypt(sealed)
    assert TOKEN not in str(err.value)


@pytest.mark.parametrize("garbage", ["not-a-token", "caf\u00e9", ""])
def test_unreadable_ciphertext_is_secrets_unavailable_without_echo(secrets_key, garbage):
    with pytest.raises(secret_box.SecretsUnavailable) as err:
        secret_box.decrypt(garbage)
    assert garbage not in str(err.value) or garbage == ""
