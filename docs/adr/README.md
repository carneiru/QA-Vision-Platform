# Architecture Decision Records

Real, accepted decisions with their evidence — extracted 2026-10-02 from
TODO.md, commit messages and benchmark rulings. Blueprint §19.2 indexes
these; target-architecture choices (Kafka, Kubernetes, Neo4j, Qdrant…) are
PROPOSED there and get an ADR when their adoption trigger fires.

| ADR | Decision |
|---|---|
| [ADR-001](ADR-001-flaky-window-rollups.md) | 90-day flaky window via daily rollups; commit rollup rejected by benchmark |
| [ADR-002](ADR-002-same-commit-semantics.md) | A duplicate inside one run is not a re-run |
| [ADR-003](ADR-003-refresh-token-httponly-cookie.md) | Refresh token as httpOnly cookie; body kept for API clients |
| [ADR-004](ADR-004-pii-masking-on-ingest.md) | PII masking at ingest, before truncation; per-project retention |
| [ADR-005](ADR-005-idempotency-body-hash.md) | Idempotency keys with body-hash replay detection |
| [ADR-006](ADR-006-sso-bypasses-mfa.md) | SSO sign-ins bypass platform MFA |
| [ADR-007](ADR-007-gateway-spa-catchall.md) | Gateway catch-all serves the SPA; /api/ keeps JSON 404 |
