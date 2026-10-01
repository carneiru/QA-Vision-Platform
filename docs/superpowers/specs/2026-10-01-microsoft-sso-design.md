# Microsoft (Entra ID) SSO — Design

**Date:** 2026-10-01
**Status:** Draft — awaiting review
**Scope:** auth-service lets people sign in with a Microsoft work or school account (Entra ID) from an allowlist of tenants, with the same protections as the existing Google sign-in, and lets a signed-in user link a Microsoft identity to their account. Plus hardening of the signing-key fetch for both providers and the stricter gateway rate limit for SSO.

## Problem

auth-service supports password login and Google SSO (`POST /api/v1/sso/google`, ID token verified against Google's keys). `POST /api/v1/sso/azure` is a placeholder that always answers 501, and the `AZURE_*` settings are unused. Teams whose identity provider is Microsoft cannot sign in with it.

## Decisions (agreed during brainstorming)

| Question | Decision |
|---|---|
| Flow | The browser obtains an **ID token** with MSAL and posts it, like Google's `credential`; no client secret, no code exchange |
| Tenants | An **allowlist** of tenant IDs (`AZURE_ALLOWED_TENANTS`); identity key `"{tid}:{oid}"` |
| Account rules | Exactly Google's: provider identity first; create new passwordless users in one transaction; never link by email (409); inactive users refused; adoption only through an authenticated link endpoint |
| Name | `microsoft` (provider, routes); the `/sso/azure` placeholder is removed |

Additions proposed while writing this spec (small, safe, flagged here so they can be dropped at review):
- `/api/v1/sso` gets the gateway's strict `auth` rate-limit zone, like password login.
- Signing-key fetch hardening for **both** providers: 5 s timeout (PyJWT's default is 30 s) and at most one forced key refresh per 5 minutes for an unknown key id.
- A rejected tenant id is logged, to make onboarding a customer's tenant easy.

## Configuration

| Setting | Meaning |
|---|---|
| `AZURE_CLIENT_ID` (exists) | The Entra app registration's client id; the required `aud` |
| `AZURE_ALLOWED_TENANTS` (new) | Comma-separated tenant ids (GUIDs). Empty → the existing `AZURE_TENANT_ID`, if set, as a one-entry list |
| `AZURE_TENANT_ID` (exists) | Kept only as that fallback, so existing `.env` files keep working |
| `AZURE_CLIENT_SECRET` (exists) | Unused (the ID-token flow needs no secret) |

Without a client id or without any allowed tenant, Microsoft sign-in is **off**: 503 `{"detail": "Microsoft SSO is not configured"}`. Verifying without an audience would accept ID tokens issued for any application.

## Token verification

`SSOService.validate_microsoft_token(token) -> dict`:

1. The signing key comes from `https://login.microsoftonline.com/common/discovery/v2.0/keys` (one key set for all tenants), through the shared hardened key client (below).
2. `jwt.decode` with `algorithms=["RS256"]`, `audience=AZURE_CLIENT_ID`, `options={"require": ["exp", "nbf", "iss", "aud", "tid", "oid"]}`.
3. `ver` must be `"2.0"` (v1 tokens, issuer `https://sts.windows.net/{tid}/`, are refused).
4. `tid` must be in the allowlist; otherwise refused, and the tenant id is logged at warning level (`tenant %s is not in AZURE_ALLOWED_TENANTS`).
5. `iss` must equal `https://login.microsoftonline.com/{tid}/v2.0` exactly.
6. Identity returned: `{"provider": "microsoft", "provider_user_id": f"{tid}:{oid}", "email": <preferred_username, or email when xms_edov is true>, "full_name": <name or None>}`. *(Revised after the final review: Entra does not verify `email` — a tenant admin can set it to anyone's address — while the UPN must be on one of the tenant's verified domains. Decoding also allows 60 s of clock leeway, since Entra sets `nbf` to the issue time.)* The email must contain exactly one `@` with text on both sides; otherwise 400 `{"detail": "Microsoft account has no email address"}`.

Errors (both providers, via one shared mapping):

| Cause | Answer |
|---|---|
| Not configured | 503 `"<Provider> SSO is not configured"` |
| Key set unreachable (`PyJWKClientConnectionError`, timeout) | 503 `"<Provider> sign-in is temporarily unavailable"` — **new for Google too**, where an outage used to read as an invalid token |
| Anything else (bad signature, claims, tenant, issuer, version, malformed) | 400 `"Invalid <Provider> token"` (Google's existing status, kept for both); details to the log only |

### Hardened key client

One small class wrapping `PyJWKClient`, used by both providers:
- HTTP timeout 5 s.
- The key set is cached (PyJWT's `cache_jwk_set`, lifespan 300 s).
- A token whose `kid` is not in the cached set may force a re-fetch **at most once per 5 minutes**; otherwise it is refused (400) without contacting the provider. Today any made-up `kid` causes a fetch from Google per request.

## Endpoints

### `POST /api/v1/sso/microsoft`

Body `{"credential": "<Microsoft ID token>"}` → `{"access_token", "refresh_token", "token_type": "bearer"}`.

Shared sign-in helper `sso_sign_in(db, identity, label)` — used by `/sso/google` too (its messages keep saying "Google"):

1. Look up `oauth_accounts` by `(provider, provider_user_id)`. Found → that user (the email on the token may have changed; it is not written back).
2. Not found, and no user has the email → create a passwordless user and the link in one transaction; a concurrent duplicate → 409 `"This <Provider> account is already linked"`.
3. Not found, and a user has the email → 409. If that user already has a link for this provider: `"This account is linked to a different <Provider> identity"`; otherwise `"An account with this email already exists. Linking <Provider> to an existing account is not supported yet."` — for Microsoft the hint points at `/api/v1/users/me/link/microsoft` (the Google message stays as it is).
4. Inactive user → 400 `"Inactive user"`.
5. Issue the access token and a refresh-token session, as today.

### `POST /api/v1/users/me/link/microsoft`

Body `{"credential": "<id_token>", "current_password": "<optional>"}`; requires a signed-in active user. Mirrors `POST /api/v1/users/me/link/google` through one shared helper:
- An account with a password must give the correct `current_password` (400 `"current_password is incorrect"`).
- The account must not already have a Microsoft link (409).
- The Microsoft identity must not be linked to anyone (409 on the unique constraint).
- Success → 200 with the user (as the Google link returns).

### Removed

`POST /api/v1/sso/azure` (always 501) and the unused `AzureLoginRequest` model. The route now answers 404.

## Gateway

`gateway/nginx.conf.template`: `location /api/v1/sso` adds `limit_req zone=auth burst=10 nodelay;` next to the `api` zone, like `/api/v1/auth/login`.

## Database

No change: `oauth_accounts` stores `provider` (50) and `provider_user_id` (255) with a unique constraint on the pair; `"{tid}:{oid}"` is 73 characters.

## Testing

No call to Microsoft or Google ever leaves the test process.

- **Token fixtures:** a test RSA key signs Microsoft-shaped ID tokens; the key client's `get_signing_key_from_jwt` is replaced with one that returns that key (as the Google tests already do). PyJWT fetches keys with `urllib`, which respx cannot intercept, so the outage cases make that function raise `PyJWKClientConnectionError`, and the key-client tests replace its `fetch_data`.
- **Verification:** valid token → identity; refused: wrong `aud`, expired, `nbf` in the future, tenant not allowed (and its id logged), `iss` not matching `tid`, `ver` "1.0", missing `tid`/`oid`, `HS256` and `none` algorithms, a signature from another key, garbage; not configured → 503; keys unreachable → 503; `AZURE_TENANT_ID` fallback when the allowlist is empty.
- **Key client:** an unknown `kid` forces one re-fetch, a second unknown `kid` within 5 minutes does not; the timeout is passed through.
- **Sign-in:** first sign-in creates a passwordless user and the link; a second sign-in with a changed email finds the same user; existing email → 409 and nothing created; the same `oid` under another allowed tenant is a different identity; inactive → 400; `preferred_username` used when `email` is absent; neither → 400.
- **Link:** requires authentication; requires `current_password` when the account has one (wrong → 400); already linked → 409; identity linked to someone else → 409; after linking, that Microsoft identity signs in to this account.
- **Google regression:** the existing Google tests pass unchanged; a Google key-fetch outage → 503.
- **Removed route:** `POST /api/v1/sso/azure` → 404 (the existing Google test that expected 501 for `azure` keeps only `github`).
- **Gateway:** `nginx -t` in CI; the smoke script checks `/api/v1/sso/microsoft` with a garbage token answers 503 through the gateway (the stack has no Microsoft configuration; reaching auth-service, not the 404 catch-all).

## Documentation

- `platforms/auth-service/auth-service/README.md`: registering the app in Entra (single-page application, ID tokens enabled, redirect URI), `AZURE_CLIENT_ID` and `AZURE_ALLOWED_TENANTS`, a minimal MSAL.js snippet that obtains the ID token and posts it, the account rules, and what is out of scope.
- `.env.example`: `AZURE_ALLOWED_TENANTS`.
- Root `README.md`: Microsoft next to Google in the feature list.
- `TODO.md`: Microsoft SSO done; the out-of-scope items below listed.

## Out of scope (TODO.md)

- Personal Microsoft accounts (outlook.com, the `consumers` tenant).
- Mapping Entra groups or app roles to organization roles.
- SCIM user provisioning and deprovisioning.
- GitHub SSO.
- Front-channel / single sign-out.
