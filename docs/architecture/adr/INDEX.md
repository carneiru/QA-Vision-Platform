# Architecture Decision Records

**Accepted** — real decisions with evidence, extracted 2026-10-02 from
TODO.md, commit messages and benchmark rulings:

| ADR | Decision |
|---|---|
| [ADR-011](ADR-011-flaky-window-rollups.md) | 90-day flaky window via daily rollups; commit rollup and join rewrite rejected by benchmark |
| [ADR-012](ADR-012-same-commit-semantics.md) | A duplicate inside one run is not a re-run |
| [ADR-013](ADR-013-refresh-token-httponly-cookie.md) | Refresh token as httpOnly cookie; body kept for API clients |
| [ADR-014](ADR-014-pii-masking-on-ingest.md) | PII masking at ingest, before truncation; per-project retention |
| [ADR-015](ADR-015-idempotency-body-hash.md) | Idempotency keys with body-hash replay detection |
| [ADR-016](ADR-016-sso-bypasses-mfa.md) | SSO sign-ins bypass platform MFA |
| [ADR-017](ADR-017-gateway-spa-catchall.md) | Gateway catch-all serves the SPA; /api/ keeps JSON 404 |
| [ADR-018](ADR-018-components-under-test.md) | Capture components-under-test per run now; correlate in Phase 6 |
| [ADR-019](ADR-019-single-vm-deployment.md) | First production deployment: one VM, Compose + Caddy TLS edge, real-IP rate limits |

**Proposed** — ADR-001..010 describe the TARGET architecture (DDD, Kafka,
Kubernetes, Go services, Neo4j, Qdrant, ...). Reclassified 2026-10-02: their
earlier "Accepted" status and 2024 provenance predate delivery and nothing in
them is deployed (the platform is Python/FastAPI + PostgreSQL throughout).
Each is adopted only when its trigger in the Blueprint's Implementation
Status banner fires. De facto accepted without ceremony: Python/FastAPI,
PostgreSQL, React + TypeScript (contradicting ADR-005's Go).
