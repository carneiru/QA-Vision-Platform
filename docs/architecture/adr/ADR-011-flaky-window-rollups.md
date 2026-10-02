# ADR-011: 90-day flaky window via daily rollups; commit rollup rejected

Status: Accepted (2026-10-02) · Evidence: scripts/analytics_benchmark.py, tests/unit/test_flaky_rollup.py

## Context
Flaky detection sorts every execution in the window. On ~2M results, 90 days
took 11.3 s live; the API was capped at 30 days.

## Decision
Daily per-(test, branch) flip aggregates in `flaky_daily` (in-day flips,
first/last outcome for day-boundary transitions, per-branch pairs = runs−1),
kept current by the `analytics-rollup` job (advisory lock, ≤90-day backfill,
yesterday+today every 6 h). Windows recombine exactly; equivalence with the
live scan is test-pinned. Cap raised to 90 days; unvisited projects fall back
to the live scan.

A first design also rolled up commit data and was **rejected by benchmark**:
with one SHA per run the commit table scales with runs×tests (2M rows) and
the rollup path measured *slower* than live (35.6 s vs 13 s). Confirmed
same-commit detection therefore stays on the live failure-driven pass.

## Consequences
90 d: 3.9 s from rollups vs 11.3 s live; 14 d: 0.83 s vs 2.1 s. Remaining
90-day cost is the confirmed pass (future optimization). ClickHouse adoption
trigger: rollups stop holding at ~10× data.

## Addendum (2026-10-02)
A follow-up experiment also rejected an aggregate-join rewrite of the
confirmed pass: 3.8 s vs the current correlated-EXISTS 1.6 s at 90 days on
the same dataset (identical result sets). The failure-driven EXISTS stands.
