# ADR-005: Idempotency keys with body-hash replay detection

Status: Accepted (2026-09) · Evidence: collect endpoint tests (replay, 409 on divergent body)

## Context
CI retries uploads; the same job must not double-ingest, but a *different*
body under a reused key is a client bug worth surfacing.

## Decision
`Idempotency-Key` + SHA of the canonical payload stored per run. Same
key+hash → replay the original receipt; same key, different hash → 409.
Collector appends a random suffix per invocation (matrix legs share CI ids)
and reuses the key only across its own retries; multi-part uploads number
their keys so re-runs replay identical parts.

## Consequences
Safe retries end-to-end; losing a receipt is recoverable by resending.
