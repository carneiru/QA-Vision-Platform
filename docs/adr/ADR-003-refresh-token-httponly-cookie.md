# ADR-003: Refresh token as httpOnly cookie; body kept for API clients

Status: Accepted (2026-10-02) · Evidence: auth tests (cookie set/rotate/replay), gateway e2e

## Context
The SPA stored the refresh token in sessionStorage — XSS-readable, an
accepted trade-off in the original dashboard spec.

## Decision
Every token-issuing endpoint also sets `qav_refresh`: httpOnly, Secure,
SameSite=Strict, Path=/api/v1/auth, 30 d. `/auth/refresh-token` and
`/auth/logout` take body **or** cookie; the body token remains issued and
accepted so non-browser clients keep working. The SPA never touches the
token: boot does one silent cookie refresh; auth/sso endpoints' own 401s
never enter the refresh flow.

## Consequences
XSS cannot exfiltrate sessions; rotation + replay-revocation semantics
unchanged; dev on http://localhost relies on browsers treating localhost as
a secure context.
