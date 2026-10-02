# QA Vision Platform — Implementation Plan

Updated 2026-10-02. Single forward plan, reconciled with TODO.md (the live
per-item record) and ARCHITECTURE_BLUEPRINT_V1_0.md (the target; its
Implementation Status banner carries the adoption triggers referenced here).
The previous version of this file was a day-one snapshot that still named
paths and phases long since superseded.

## 1. Done (verified, running, tested)

| Phase | Delivered |
|---|---|
| 1. Platform foundation | auth-service (JWT rotation + replay detection, email-verified registration, Google/Microsoft SSO with tenant allowlist, TOTP MFA + recovery codes, httpOnly refresh cookie), organization-service (orgs/members/roles/invitations), project-service (projects/settings/internal retention API), NGINX gateway (rate zones, TLS, JSON errors, request IDs), compose stack, CI with full-stack smoke |
| 2. Ingestion | ingestion-service collect API (API keys, idempotency+replay, PII masking, retention job), qav-collector (JUnit incl. Surefire rerun attempts, CI detection, git code-change data, retrying multi-part uploads) |
| 3. Analytics + UI | Analytics API (trends day/week/month, tests, history, flaky ≤90 d via daily rollups + rollup job, branches, mute/unmute), React dashboard (login/MFA/SSO, picker, all analytics views, runs browser incl. changed files, CSV export, account security), 20/20 design audit |

Benchmarked: flaky 90 d 3.9 s (rollups) vs 11.3 s live on ~2M results; full
numbers in platforms/ingestion-service/README.md.

## 2. Now / Next (small, unblocked — TODO.md carries the authoritative list)

1. Git metadata on runs: commit author/message, PR number, base branch
   (pairs with shipped code-change data).
2. ~~Collector `--ca-file` fix~~ — done: `--ca-file` now pins trust exclusively (curl `--cacert` semantics); blending with the system store broke on Windows machines with CN=localhost dev certs in ROOT.
3. ~~Confirmed-flaky pass optimization~~ — investigated 2026-10-02 and
   closed without change: on the 2M-row benchmark the current failure-driven
   correlated-EXISTS pass measures 1.6 s at 90 d and beats an aggregate-join
   rewrite (3.8 s, identical result sets). The confirmed pass is a minority
   of the 90-day total; revisit only if real data shows otherwise.
4. Collector distribution (a product slice of its own — full list in
   TODO.md "Collector — nice to have"): tag `collector-v0.1.0`; PyPI trusted
   publishing (`pip install qav-collector`); ready-made GitHub Action and
   GitLab component; Jenkins shared-library step; zipapp/Docker builds;
   then formats (Cucumber JSON, Playwright JSON, TestNG/NUnit/xUnit/TRX) and
   reliability (`qav-collector check`, keep-and-retry failed uploads,
   partial streaming).
5. Phase 2 exit proof: agents on 3 CI platforms in real projects; 10k real
   executions ingested.

## 3. Blocked on external input

- SAML 2.0 sign-in and real-tenant SSO verification: need an IdP / client
  IDs (note: `collaboration/` vendors an xmlsec source tree usable for SAML).
- Production deployment target (cluster, domain, real certificates).

## 4. Later — target-architecture slices, each behind its blueprint trigger

| Slice | Trigger |
|---|---|
| Queue-based ingestion (Kafka) | sustained 1000+ events/s or CI-visible upload latency |
| Redis shared rate limits / cache | second gateway instance |
| ClickHouse analytics warehouse | rollups stop holding at ~10× data |
| Artifact storage (MinIO) | artifacts feature starts (screenshots/videos/traces) |
| Kubernetes + real certs + monitoring stack (Prometheus server/Grafana) | first multi-node deployment |
| Test Management service (blueprint capability) | product pull, after Phase 2 exit |
| Phase 6 AI engine, QIP services, vector/graph stores | AI work begins; revive or replace the `intelligence/` prototype deliberately |

## 5. Prototype directories

`execution/`, `automation/`, `marketplace/`, `collaboration/`,
`intelligence/`, `platforms/qip-service` are unwired prototypes (no compose,
CI, gateway, migrations). Decision pending: archive to a branch or revive
per-slice when their capability's trigger fires. Do not treat their presence
as shipped functionality.

## 6. Working agreement

- TODO.md is updated in the same commit as the work it records.
- Direct pushes to master; all relevant suites green before every push; TDD
  for behavior changes.
- Every new feature names the blueprint section it serves or amends; pulling
  a TARGET technology requires citing its trigger.
