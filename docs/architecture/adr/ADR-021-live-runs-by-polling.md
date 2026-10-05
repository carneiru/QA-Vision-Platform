# ADR-021: New runs reach the dashboard by polling, not WebSockets (for now)

Status: Accepted (2026-10-05) · Evidence: dashboard `src/lib/live.ts`, `RunsPage.test.tsx` and `OverviewPage.test.tsx` live tests

## Context
Roadmap Phase 3, step 7 asks for "real-time updates via WebSockets". The real-time spec
(`docs/superpowers/specs/2026-07-13-qa-vision-realtime-features.md`) designs a WebSocket
gateway with a message broker behind it.

The data does not support that yet:

- The collector uploads once a CI job has finished. Nothing reaches the platform while
  tests are still running.
- A new run therefore appears every few minutes at most, and per project far less often.

A push channel would also need a fan-out between ingestion workers and every open
dashboard: Redis pub/sub or a broker. The Blueprint gates both behind triggers that have not
fired: a second gateway instance for Redis, and sustained load for Kafka. It would also need
WebSocket handling in the NGINX gateway and authentication on long-lived connections.

## Decision
- Views that show the newest runs poll every 30 seconds (`LIVE_REFRESH_MS`). These are the
  first page of **Runs** and the **Overview**.
- TanStack Query pauses polling while the tab is hidden and refetches when it regains focus.
- The Runs view keeps a reader's place:
  - later pages never refresh on their own;
  - new rows get a short tint;
  - a polite status region announces the count, for example "2 new runs".
- The Overview also refreshes the week's pass rate and the flaky count when the latest run
  changes.
- There is no new endpoint. The poll reuses the indexed runs list (`limit` 50, or 1 on the
  Overview).

## Consequences
- A new run shows up within about 30 seconds without a reload. The services and the gateway
  do not change.
- Cost: one small indexed query per visible tab every 30 seconds, which is negligible at
  current scale.
- This does not provide live progress of a run that is still executing. That needs the
  collector to stream partial results, which TODO.md lists and defers.

## Adoption trigger for push (SSE or WebSockets)
Revisit when either of these holds:

- the collector streams partial results during a run, so seconds matter; or
- open dashboards make polling a measurable share of ingestion load.

At that point, start with server-sent events. They are one-way, which is all this needs,
and they pass through the NGINX gateway with buffering turned off. Fan out through Redis
pub/sub; its adoption trigger fires with that change.
