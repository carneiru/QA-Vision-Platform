# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two confirmed audiences, served equally:

- **QA / SDET engineers** triaging CI results daily: which tests failed, which
  are flaky, what regressed on which branch or environment. Per-test
  drill-down is their job.
- **Engineering managers** reading suite health weekly: pass-rate trends, run
  volume, flaky counts. Aggregates over drill-down.

## Product Purpose

QA Vision ingests test results from any CI (JUnit XML via the `qav-collector`
agent), stores them per project, and turns them into analytics: daily trends,
per-test statistics and history, and flaky-test detection. Success: a team
answers "what is broken, what is flaky, what is getting worse" from one place
instead of scrolling CI logs.

## Positioning

AI-powered test analysis is the destination (Phase 6: failure pattern
recognition, risk-based prioritization, predictive analytics — not yet
built). Today's honest claim: a self-hosted platform whose flaky detection
distinguishes **confirmed** flakiness (same commit + environment, both passed
and failed) from **suspected** (statistical flip rate) — present that
distinction, never blur it. Do not market AI capabilities that do not exist
yet.

## Operating Context

- Results arrive from CI (GitHub Actions, GitLab CI, Jenkins) via the
  collector; engineers open the dashboard after a red build or when a flaky
  ticket lands; managers open it in weekly reviews.
- Microservices behind one NGINX gateway: auth-service (JWT, Google and
  Microsoft SSO), organization-service (orgs, members, roles),
  project-service, ingestion-service (runs, results, analytics API),
  `dashboard/` (React SPA, in progress on `feat/dashboard-ui`).
- Everything is deployed as containers from the repository-root
  docker-compose; same-origin API at `/api/v1/*`.

## Capabilities and Constraints

- Analytics API (read-only): daily trends in any IANA time zone; per-test
  list, history; flaky detection with `window_days` capped at 30 for
  performance (10.8 s at 90 days on 2M results — documented ruling).
- Access model: organization membership grants project access; roles are
  owner/admin/member.
- `test_key` values contain `/`, `::`, spaces — always URL-encoded.
- `pass_rate` is a 0..1 fraction or null; null renders as "—".
- Internal tool: every dashboard surface is an authenticated Operate
  surface. No marketing or landing pages are planned.

## Evidence on Hand

- Real ingested runs exist only in dev/test stacks; production data is
  per-deployment. Screens show real ingested data or honest empty states —
  never fabricated metrics, testimonials, or benchmarks.
- Benchmarks documented in `platforms/ingestion-service/README.md`.

## Product Principles

1. Truth over polish: numbers shown are exactly what the API computed;
   absence of data is shown as absence, not zero.
2. Triage speed first: an engineer lands on "what is broken now" in one
   screen; depth (history, commits) is one click away.
3. Confirmed vs suspected is a first-class distinction wherever flakiness
   appears.
4. Same platform truth for both audiences: managers get aggregates of the
   same data engineers drill into, not a separate metric set.
5. Self-hosted modesty: no claims (AI or otherwise) ahead of shipped
   capability.

## Accessibility & Inclusion

- WCAG AA: chart and table contrast meets AA; status is never conveyed by
  color alone (labels/legends always present); colorblind-validated status
  palette (passed #0ca30c, failed #d03b3b, errored #ec835a, skipped #898781).
- Dark and light mode are both first-class, following the OS preference.
