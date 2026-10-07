# QEOS — Technical Specification (Current State)

Updated 2026-10-02. This document specifies the system **as it runs today**.
The target architecture lives in ARCHITECTURE_BLUEPRINT_V1_0.md (see its
Implementation Status banner and adoption triggers); the delivery record is
TODO.md; the forward plan is IMPLEMENTATION_PLAN.md. The previous version of
this file duplicated Blueprint §5–§11 and described an unbuilt system.

## 1. System Overview

Four FastAPI services behind one NGINX gateway, a React SPA, a CLI collector
agent, and two background jobs — all on PostgreSQL 15, all deployed via the
repository-root docker-compose.

```
qeos-collector (CI) ──► gateway ──► ingestion-service ──► ingestion_db
browser (dashboard SPA) ─► gateway ─► auth / organization / project / ingestion
jobs: ingestion-retention, analytics-rollup (ingestion image, advisory locks)
```

All cross-service communication is synchronous HTTP through the gateway or
the internal project-service API. No event bus exists (Kafka is a blueprint
target gated on the 1000+ events/s trigger).

## 2. Services

### 2.1 auth-service (`platforms/auth-service/auth-service`)
- Registration with email verification (PendingRegistration → User on
  GET /auth/verify-email; unverified addresses are unclaimed).
- Login: JWT access token (60 min) + opaque refresh token (30 d, DB-stored,
  rotated on use, replay ⇒ every session revoked). Refresh token also set as
  httpOnly cookie `qeos_refresh` (Secure, SameSite=Strict, Path=/api/v1/auth);
  body token kept for API clients; `/auth/refresh-token` and `/auth/logout`
  accept body or cookie. The pre-rename cookie `qav_refresh` is still read when
  `qeos_refresh` is absent; every token issue clears it, and logout clears both
  cookies and revokes the session behind each.
- MFA (TOTP): `/auth/mfa/enroll|confirm|disable`; login answers
  `{mfa_required, mfa_token}` (5-min purpose-bound JWT) and
  `/auth/mfa/verify` completes with a TOTP or single-use recovery code
  (8 issued once, bcrypt-hashed). SSO sign-ins bypass MFA (IdP's factor).
- SSO: `/sso/google`, `/sso/microsoft` verify provider ID tokens
  (`{credential}`) against JWKS; Microsoft restricted to AZURE_ALLOWED_TENANTS;
  signing-key fetch hardened (timeout, throttled refresh; outages ⇒ 503).
  `/sso/github` is an honest 501.

### 2.2 organization-service
Organizations (soft delete), members (owner/admin/member/viewer/
billing_manager), invitations (accept flow), `GET /organizations` lists the
caller's active memberships with role. Role checks via JWT `sub` + membership.

### 2.3 project-service
Projects under organizations (access follows org roles), settings
(result_retention_days, default_environment), repositories, internal
retention endpoint (HTTP Basic, INTERNAL_API_PASSWORD) consumed by the
retention job.

### 2.4 ingestion-service
- **Collect**: `POST /collect/runs` with project API key (`qeos_` bearer; keys issued
  before the QEOS rename start with `qav_` and are still accepted).
  Validation (extra="forbid"), idempotency keys with body-hash replay
  detection, PII masking before truncation, server-computed counts, optional
  `changes` block (base ref + ≤1000 changed files; git name-status letters;
  null additions/deletions for binary).
- **Read**: runs list per project (filters: branch, failing/passing, environment, CI, commit
  prefix, PR, author, started-at range), run detail with status filter and changed
  files. Access: user JWT + project role via project-service.
- **Analytics** (read roles): trends (`bucket=day|week|month`, Monday weeks,
  any IANA tz, ≤365 d), per-test list (sort/search/limit≤200/offset),
  history (encoded test_key), flaky (`window_days≤90`, min_runs,
  min_flip_rate, branch, include_muted), branches (per-branch aggregates),
  flaky mute/unmute (edit roles).
- **Jobs**: `ingestion-retention` (per-project retention + deleted-project
  cleanup, pg advisory lock 7351001); `analytics-rollup` (flaky_daily
  backfill ≤90 d + yesterday/today every 6 h, lock 7351002).

### 2.5 test-management-service (`platforms/test-management-service`, ADR-022)
- **Cases**: per-project numbers shown as `TC-n` (never reused; archive, no delete), title,
  description, up to 50 `{action, expected}` steps, up to 20 lower-case labels, priority,
  status (draft/ready/archived), optional link to an automated test (`automated_test_key`, the
  ingestion `test_key`; the dashboard reads its latest result from ingestion).
- **Lists**: search (title), label (ANDed), status, priority, paging; `GET /case-labels`
  counts labels in use.
- **Suites**: unique name per project, ordered cases replaced as a whole by
  `PUT /suites/{id}/cases` (≤1000, unknown or repeated numbers are a 422); deleting a suite keeps
  its cases.
- Access: user JWT + project role via project-service (every role reads; owner/admin/member
  edit), the same contract as ingestion. The client is a copy of ingestion's (ADR-022).

## 3. Data

PostgreSQL 15; one database per service (auth_db, organization_db,
project_db, ingestion_db, testmgmt_db), created by db-init, migrated by per-service
Alembic jobs. Only the owning service writes its database; cross-domain
reads go through APIs (blueprint principle, enforced in practice).

Key ingestion tables: test_runs (+ change summary columns), test_results
(message/details masked+truncated, `(test_key, run_id)` index),
run_changed_files, muted_tests, flaky_daily / flaky_rollup_days (daily flip
aggregates + computed-day markers), api_keys.

## 4. Flaky Detection Semantics (rulings)

- **Confirmed (`same_commit`)**: the test passed and failed for one
  (commit, environment) across *different* runs — a duplicate inside one run
  is not a re-run.
- **Suspected (`flips`)**: outcome changes between consecutive executions,
  counted per branch; skipped excluded; errored↔failed is not a flip.
- Windows ≤90 d recombine exactly from `flaky_daily`
  (in-day flips + day-boundary transitions; pairs = per-branch runs−1);
  equivalence with the live scan is pinned by unit tests. Projects the
  rollup job has not visited fall back to the live scan.
- Measured (≈2M results): flaky 90 d 3.9 s from rollups vs 11.3 s live;
  14 d 0.83 s. Remaining 90 d cost is the failure-driven confirmed pass.

## 5. Gateway

NGINX: TLS (self-signed in dev), per-IP rate zones (`api`; stricter `auth`
zone on login/sso/mfa-verify), JSON error pages, request IDs, regex routes
sending `/projects/{id}/(api-keys|runs|analytics|…)` to ingestion and
`/projects/{id}/(cases|case-labels|suites)` to test-management, SPA
catch-all to the dashboard container with JSON 404 preserved for unrouted
`/api/` paths; `/metrics` and `/internal` are never proxied.

## 6. Dashboard (`dashboard/`)

React 18 + Vite + TypeScript, TanStack Query, Recharts (lazy chunks for
chart views). Access token in memory; session restored at boot via the
httpOnly cookie; 401s refresh once (auth/sso endpoints excluded). Views:
login (password/MFA step/SSO buttons when VITE_* client ids are baked),
org→project picker, trends (day/week/month), tests, history, flaky
(mute/unmute, CSV export), branches (pick-two pass-rate comparison), runs
(list + detail incl. changed files), account security (TOTP enrollment).
Design tokens with light/dark modes; WCAG AA contrast; status never
color-alone (PRODUCT.md commitments).

## 7. Collector (`collector/`)

`qeos-collector upload`: JUnit XML (pytest, Surefire incl.
flaky/rerun attempt expansion, Playwright, cucumber-js), CI detection
(GitHub Actions/GitLab/Jenkins), git code-change data
(GITHUB_BASE_REF / MR target / commit parent; never blocks an upload),
retry-safe idempotency keys, multi-part past 20k results / 9 MB, 2-minute
retry budget, verified TLS (`--ca-file` for private CAs; known issue: the
dev gateway's self-signed cert is still rejected — see TODO).

## 8. Verification

- Per-service pytest suites (auth 120, organization 95, project, ingestion
  390) + shared tests, collector 139 (Python 3.9/3.12), dashboard 67 Vitest
  (Testing Library + MSW) + tsc + eslint + build.
- CI (`.github/workflows/ci.yml`): service matrix, collector matrix,
  dashboard job, per-service container smoke, gateway full-stack smoke
  (`scripts/smoke_gateway.sh`, 70+ checks), CodeQL.
- `scripts/analytics_benchmark.py`: seeded ~2M-result benchmark; results
  recorded in platforms/ingestion-service/README.md.
- Workflow: direct pushes to master, full relevant suites green before every
  push; TDD (tests watched failing first) for behavior changes.

## 9. Explicitly Not Built (see blueprint triggers)

Event bus/Kafka, CDC, data lake/warehouse, knowledge graph, vector store,
Redis, MinIO, Elasticsearch, Kubernetes/service mesh/Vault/GitOps, QIP
services, SDKs, mobile. `execution/`, `automation/`, `marketplace/`,
`collaboration/`, `intelligence/`, `platforms/qip-service` are unwired
prototypes excluded from compose/CI/gateway.
