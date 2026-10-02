# ADR-016: SSO sign-ins bypass platform MFA

Status: Accepted (2026-10-02) · Evidence: login flow (mfa_required only on password path), MFA tests

## Context
TOTP MFA shipped for password accounts; Google/Microsoft sign-ins verify
provider ID tokens.

## Decision
The MFA challenge applies to password logins only. Identity-provider
sign-ins inherit the IdP's own MFA posture (Entra CA policies etc.);
double-prompting adds friction without adding factors we control.

## Consequences
Org-wide MFA enforcement for SSO users is the IdP's configuration, not
ours; a platform policy layer (require MFA per org) remains future work.
