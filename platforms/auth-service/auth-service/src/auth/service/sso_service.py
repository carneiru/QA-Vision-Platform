"""SSO Service — real Google ID token verification.

This previously returned hardcoded identities for every provider (`user@gmail.com` and
friends) while the endpoint went on to mint real access and refresh tokens for whatever
that mock returned. Any credential string would have been accepted. It was never reachable
in practice only because this module's importers did not parse, but it was one syntax fix
away from being an unauthenticated login-as-anyone hole.

Google is now verified properly against Google's published signing keys. GitHub and Azure
are not implemented and their endpoints say so (501) rather than pretending.
"""

import jwt
from jwt import PyJWKClient

from src.auth.config import settings

# Google publishes the public keys for its ID tokens here.
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# Google sets one of these two as `iss` on ID tokens.
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# Module-level so the fetched key set is cached across requests rather than re-fetched per login.
_jwks_client = PyJWKClient(GOOGLE_CERTS_URL)


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
