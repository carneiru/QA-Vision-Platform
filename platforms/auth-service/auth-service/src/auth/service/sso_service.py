"""SSO Service — real Google ID token verification.

This previously returned hardcoded identities for every provider (`user@gmail.com` and
friends) while the endpoint went on to mint real access and refresh tokens for whatever
that mock returned. Any credential string would have been accepted. It was never reachable
in practice only because this module's importers did not parse, but it was one syntax fix
away from being an unauthenticated login-as-anyone hole.

Google is now verified properly against Google's published signing keys. GitHub and Azure
are not implemented and their endpoints say so (501) rather than pretending.
"""

import logging
import re
import time
from typing import Callable, Optional

import jwt
from jwt import PyJWK, PyJWKClient, PyJWKClientError

from src.auth.config import settings

logger = logging.getLogger(__name__)

KEY_FETCH_TIMEOUT_SECONDS = 5
KEY_REFRESH_INTERVAL_SECONDS = 300


class ThrottledJWKClient(PyJWKClient):
    """PyJWKClient with a short timeout and a limit on forced key-set refreshes.

    PyJWKClient re-fetches the key set whenever a token names a key id it has not cached, so a
    token with a made-up `kid` made us call the provider on every request (and wait up to 30 s,
    PyJWT's default timeout). Here an unknown key id forces a re-fetch at most once per refresh
    interval; otherwise it is refused without contacting the provider.
    """

    def __init__(
        self,
        uri: str,
        *,
        timeout: int = KEY_FETCH_TIMEOUT_SECONDS,
        refresh_interval: float = KEY_REFRESH_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        super().__init__(uri, cache_jwk_set=True, lifespan=300, timeout=timeout)
        self._refresh_interval = refresh_interval
        self._clock = clock
        self._last_forced_refresh: Optional[float] = None

    def get_signing_key(self, kid: str) -> PyJWK:
        signing_key = self.match_kid(self.get_signing_keys(), kid)
        if signing_key is None:
            now = self._clock()
            recently = (
                self._last_forced_refresh is not None
                and now - self._last_forced_refresh < self._refresh_interval
            )
            if recently:
                raise PyJWKClientError(f'Unable to find a signing key that matches: "{kid}"')
            self._last_forced_refresh = now
            signing_key = self.match_kid(self.get_signing_keys(refresh=True), kid)
            if signing_key is None:
                raise PyJWKClientError(f'Unable to find a signing key that matches: "{kid}"')
        return signing_key


class SSOIdentityError(Exception):
    """The token is genuine but its identity cannot be used. The message is shown to the caller."""

# Google publishes the public keys for its ID tokens here.
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# Google sets one of these two as `iss` on ID tokens.
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# Module-level so the fetched key set is cached across requests rather than re-fetched per login.
_jwks_client = ThrottledJWKClient(GOOGLE_CERTS_URL)


class SSOConfigurationError(Exception):
    """Raised when a provider is enabled in code but not configured with its client id."""


class SSOService:
    @staticmethod
    async def validate_google_token(token: str) -> dict:
        """Verify a Google ID token and return the identity it asserts.

        Raises on anything short of a valid, correctly-audienced, unexpired token signed by
        Google. Callers must treat any exception as an authentication failure -- never fall
        back to a default identity.
        """
        if not settings.GOOGLE_CLIENT_ID:
            # Fail closed. Verifying without an audience would accept ID tokens minted for
            # *any* Google client -- i.e. any other application's users could log in here.
            raise SSOConfigurationError(
                "GOOGLE_CLIENT_ID is not configured; refusing to verify Google ID tokens"
            )

        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )

        # Checked here rather than via jwt.decode(issuer=...): PyJWT 2.8.0 compares iss with
        # a plain !=, so passing the two-element tuple Google actually uses rejected every
        # real token. Accepting a list only landed in PyJWT 2.10.
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise ValueError(f"unexpected issuer: {claims.get('iss')!r}")

        if not claims.get("email"):
            raise ValueError("Google ID token carries no email claim")

        # Require an explicit boolean true. Checking `is False` let an absent claim -- or a
        # string "false", which some Google surfaces have emitted -- through, which defeats
        # the point: an unverified address is one the caller may not control.
        if claims.get("email_verified") is not True:
            raise ValueError("Google ID token's email is not verified")

        return {
            "email": claims["email"],
            "full_name": claims.get("name"),
            "provider": "google",
            "provider_user_id": claims["sub"],
        }
