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
            issuer=list(GOOGLE_ISSUERS),
            options={"require": ["exp", "iss", "aud", "sub"]},
        )

        if not claims.get("email"):
            raise ValueError("Google ID token carries no email claim")

        # Google sets email_verified=False for addresses it has not confirmed; accepting
        # those would let someone claim an address they do not control.
        if claims.get("email_verified") is False:
            raise ValueError("Google ID token's email is not verified")

        return {
            "email": claims["email"],
            "full_name": claims.get("name"),
            "provider": "google",
            "provider_user_id": claims["sub"],
        }
