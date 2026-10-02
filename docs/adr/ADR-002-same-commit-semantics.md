# ADR-002: A duplicate inside one run is not a re-run

Status: Accepted (2026-10-01) · Evidence: analytics_service.mixed_commits (other_run.id != Run.id), test suite

## Context
"Confirmed" flakiness means pass+fail on one (commit, environment). A single
upload may legitimately contain the same test twice (sharded suites,
parametrization collisions, Surefire attempt expansion).

## Decision
Same-commit confirmation requires the pass in a *different* run of that
commit+environment. In-run pass/fail pairs surface through flip counting and
the run detail, never the "confirmed" badge.

## Consequences
Retry-attempt expansion (collector) cannot fabricate confirmed flakiness;
CI shards re-running a commit still confirm correctly.
