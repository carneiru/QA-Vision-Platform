# ADR-014: PII masking at ingest, before truncation; retention per project

Status: Accepted (2026-09) · Evidence: ingest_service.mask/truncate order, retention job, masking tests

## Context
Test output (messages/details) carries secrets and PII; storage must be safe
by default and data must expire.

## Decision
Mask free text on ingest (identity fields reject unstorable content instead),
and mask **before** truncating — a cut through a secret would leave its first
half unmatched. Retention job deletes runs past each project's
result_retention_days and empties deleted projects; a pass that cannot get a
trustworthy policy answer deletes nothing.

## Consequences
Raw secrets never persist; masking counts exported as metrics; old data
pre-masking is re-masked on demand by `python -m src.ingestion.jobs.remask` (idempotent).
