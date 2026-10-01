import json

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClientError
from jwt.algorithms import RSAAlgorithm

from src.auth.service.sso_service import ThrottledJWKClient


def make_client(now):
    client = ThrottledJWKClient("https://keys.example.test/", clock=lambda: now[0])
    public = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    jwk = json.loads(RSAAlgorithm.to_jwk(public))
    jwk.update({"kid": "k1", "use": "sig", "alg": "RS256"})
    fetches = []

    def fake_fetch():
        fetches.append(1)
        data = {"keys": [jwk]}
        client.jwk_set_cache.put(data)
        return data

    client.fetch_data = fake_fetch
    return client, fetches


def test_a_known_kid_is_served_from_the_cache():
    client, fetches = make_client([1000.0])
    assert client.get_signing_key("k1").key_id == "k1"
    assert client.get_signing_key("k1").key_id == "k1"
    assert len(fetches) == 1


def test_an_unknown_kid_forces_at_most_one_refresh_per_interval():
    now = [1000.0]
    client, fetches = make_client(now)
    client.get_signing_key("k1")
    assert len(fetches) == 1

    with pytest.raises(PyJWKClientError):
        client.get_signing_key("made-up-1")
    assert len(fetches) == 2  # one forced refresh

    with pytest.raises(PyJWKClientError):
        client.get_signing_key("made-up-2")
    assert len(fetches) == 2  # refused without contacting the provider

    now[0] += 301
    with pytest.raises(PyJWKClientError):
        client.get_signing_key("made-up-3")
    assert len(fetches) == 3


def test_the_fetch_timeout_is_short():
    assert ThrottledJWKClient("https://keys.example.test/").timeout == 5
