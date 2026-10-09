# ADR-026: The report joins in the dashboard; run origin is matched by CI run URL

Status: Accepted (2026-10-08) · Spec: `docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md`

## Context
The Report page needs filters that live in two services: branch, environment, CI provider and run
data in ingestion; Gherkin features, folders, labels and suites in test-management. ADR-022 says
services never call each other. People also want to tell runs started from QEOS (Play, ADR-025)
from ordinary CI runs, and no upload carries that fact.

## Decision
- **The dashboard joins.** Test-management serves every active case once, dictionary-encoded
  (`GET /case-areas`, 409 above 50,000 cases). The dashboard turns an area or suite filter into
  test keys and sends them to ingestion's one report endpoint (`POST /analytics/report`, at most
  20,000 keys, one array parameter on PostgreSQL). In phase 3 the dashboard also groups
  ingestion's per-test rows by area.
- **Origin is matched by URL.** A run is "requested from QEOS" when `ci_provider = github_actions`
  and `lower(ci_run_url)` is one of the Play requests' `github_run_url`s
  (`GET /run-requests/run-urls`). Every other run is CI. Shards and re-run attempts share the URL,
  so they count as the same Play.
- **Known limits:** a Play whose GitHub run was never matched counts as CI; runs outside GitHub
  Actions are always CI.
- **The report's default branch** is the first repository's default branch (project-service), else
  `main`; `branch=*` in the URL means every branch.
- Only `case-areas` and `analytics/report` are gzipped at the gateway (BREACH).

## Alternatives rejected
- **A stored origin marker** (a Play workflow input, a collector field, an ingestion column and a
  backfill). Worth it only if the URL match proves unreliable; listed in TODO.md.
- **Inferring origin from `ci_provider`.** A Play run is an ordinary `github_actions` run.
- **Ingestion calling test-management for areas.** Breaks ADR-022 and couples the services' uptime.

## Consequences
- Request bodies on the report can be large. The 1.4 MB figure counts only the keys (20,000 x about 65 bytes). With 5,000 Play URLs at about 70 characters each, a typical body is about 1.75 MB, within the gateway's 10 MB `client_max_body_size`. The worst case (5,000 URLs at the full 2,048 characters, about 10 MB, plus the keys) exceeds that cap, and the gateway answers 413.
- The report's area filters only see automated tests linked to a case; the Coverage section (phase
  3) counts the others.
