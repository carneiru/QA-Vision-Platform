"""SSO Service -- not implemented.

This used to return hardcoded identities for every provider (a fixed email, a fixed
provider_user_id), so any caller that reached these methods authenticated as that identity
regardless of what token or code they presented. Because this file is a scaffolding
template, that mock was copied into every service scaffolded from it -- 17 services
carried the same auth bypass before the clones were deleted and this template fixed.

Whoever wires SSO into a real service built from this skeleton must implement real
verification (see platforms/auth-service/auth-service/src/auth/service/sso_service.py for
the pattern: JWKS signature verification, audience/issuer/expiry checks, verified-email
enforcement) before these methods do anything but raise.
"""


class SSOService:
    @staticmethod
    async def validate_google_token(token: str) -> dict:
        raise NotImplementedError("Google SSO is not implemented in this skeleton")

    @staticmethod
    async def exchange_github_code(code: str) -> dict:
        raise NotImplementedError("GitHub SSO is not implemented in this skeleton")

    @staticmethod
    async def exchange_azure_code(code: str, tenant_id: str) -> dict:
        raise NotImplementedError("Azure AD SSO is not implemented in this skeleton")
