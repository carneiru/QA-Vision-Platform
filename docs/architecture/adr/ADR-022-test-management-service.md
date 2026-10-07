# ADR-022: Test management is its own service, started before the Phase 2 exit

Status: Accepted (2026-10-06) · Spec: `docs/superpowers/specs/2026-10-06-test-management-design.md`

## Context
The Blueprint lists Test Management as a platform capability of its own. IMPLEMENTATION_PLAN §4
places it "after Phase 2 exit", on product pull. The Phase 2 exit is not proven yet: it needs
agents on three CI platforms in real projects and 10 000 real executions.

On 2026-10-06 the user asked for it now, and chose two things:

- a separate service, over tables inside ingestion-service;
- a first slice of cases, suites and the link to automated tests.

## Decision
- Build `test-management-service` now, as its own FastAPI service with its own database
  (`testmgmt_db`).
- Authorisation comes from project-service's project role, the same contract ingestion uses.
- The link to automated results is only a `test_key`. The dashboard joins the two sides, so the
  services do not call each other.
- The product pull overrides the Phase 2 sequencing, on the user's decision. The Phase 2 exit
  work (real pipelines) stays open and is not blocked by this.

## Consequences
- One more container, database, CI matrix entry and gateway route.
- The project-role client and the auth dependencies are now copied in two services.
  - Moving them into `qeos_shared` is the obvious follow-up once a third copy appears.
  - Until then the copies are kept identical, and their tests mirror each other.
- Executing suites from QEOS (backlog B) will need this service and ingestion to agree on
  run ↔ suite links. That is designed when execution starts, not now.
