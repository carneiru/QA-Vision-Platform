# ADR-007: Gateway catch-all serves the SPA; /api/ keeps the JSON 404 contract

Status: Accepted (2026-10-01, amended 2026-10-02) · Evidence: smoke_gateway.sh checks, gateway review finding

## Context
The dashboard shares the API's origin (no CORS); deep links must serve
index.html; previously `location /` returned 404 and that fall-through was a
security assertion for /metrics and /internal.

## Decision
`location /` proxies to the dashboard container (its nginx falls unknown
paths back to index.html, hashed assets immutable-cached). A `location /api/`
guard keeps unrouted API paths answering the gateway's JSON 404 — scripts and
JSON clients never receive HTML 200s. /metrics and /internal now serve SPA
HTML, asserted leak-free in smoke (never proxied).

## Consequences
One origin, SPA routing works; the old "unknown = 404" contract survives
exactly where machines depend on it.
