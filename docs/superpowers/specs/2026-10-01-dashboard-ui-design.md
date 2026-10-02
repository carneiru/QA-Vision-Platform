# Dashboard UI (Analytics MVP) — Design

Date: 2026-10-01
Status: Approved (design); implementation pending
Depends on: Analytics API (PR #14, `feat/analytics-api`)

## Purpose

A web UI for the Analytics API: trends, per-test statistics, test history and
flaky-test detection, scoped to a project. First frontend in the platform.
Closes the "Dashboard UI" item under "Analytics API (Phase 3, step 1)" in
TODO.md.

Success criteria: a user can log in with email/password, pick a project, and
read all four analytics views against live data through the gateway, with the
same filters the API offers.

## Scope

In scope (MVP):

- Login (email/password through the gateway), token refresh, logout
- Organization → project picker
- Trends view (daily chart with filters)
- Tests view (sortable, searchable, paginated table)
- Test history view (summary plus execution list)
- Flaky tests view (reason, flip rate, tuning controls)

Out of scope (deferred):

- SSO sign-in buttons (Google, Microsoft)
- Mute / acknowledge a flaky test (needs a write API first)
- CSV export, branch comparison, weekly/monthly views
- Org/project/member management, runs browser, WebSockets

## Stack

- React 18, Vite, TypeScript, React Router
- TanStack Query for server state; no global state library
- Recharts for charts
- Vitest + React Testing Library + MSW for tests
- Multi-stage Dockerfile: `node` build stage → `nginx` static-serve stage

Rationale: SPA built to static files fits the existing nginx gateway and the
all-container deployment; TypeScript types mirror the Pydantic response
models; four endpoints do not justify OpenAPI codegen.

## Placement and serving

- New top-level `dashboard/` directory (peer of `collector/`, not under
  `platforms/` — it is not a FastAPI service).
- New `dashboard` service in the root `docker-compose.yml` (nginx serving the
  built assets).
- Gateway change: `location /` proxies to the dashboard service instead of
  returning 404. The dashboard's own nginx falls back unknown paths to
  `index.html` (SPA routing). All `/api/*`, `/health*` and error locations in
  the gateway stay as they are and keep winning over `/` by specificity.
- Same origin as the API, so no CORS changes.

## Authentication

- Login page posts to `POST /api/v1/auth/login`; response carries access and
  refresh tokens.
- Access token lives in memory only (module-level, never persisted).
- Refresh token lives in `sessionStorage` (per-tab, cleared on close).
  Accepted trade-off for the MVP; httpOnly-cookie refresh needs an
  auth-service change and is deferred.
- On any 401, the client attempts one silent refresh
  (`POST /api/v1/auth/refresh-token`, rotation-aware: the new refresh token replaces
  the stored one), then retries the request once; if refresh fails, clear
  tokens and redirect to `/login`.
- Logout calls the auth-service logout endpoint and clears both tokens.

## Routes and views

| Route | View |
| --- | --- |
| `/login` | Email/password form |
| `/` | Org → project picker (`GET /api/v1/organizations`, `GET /api/v1/organizations/{id}/projects`) |

**Backend prerequisite discovered during design:** organization-service has no
"list my organizations" endpoint (only `GET /{org_id}`). This feature adds
`GET /api/v1/organizations` — organizations where the current user is a
member, with their role, read from `OrganizationMember` — plus tests. The
gateway's `/api/v1/organizations` prefix location already routes it. Without
it the picker cannot enumerate organizations.
| `/projects/{id}` | Redirects to trends |
| `/projects/{id}/trends` | Trends chart |
| `/projects/{id}/tests` | Tests table |
| `/projects/{id}/tests/{testKey}` | Test history |
| `/projects/{id}/flaky` | Flaky tests |

Project pages share a layout: project name, tab navigation between the four
views, shared filter bar where filters apply to the view.

### Trends — `GET /api/v1/projects/{id}/analytics/trends`

- Stacked bars per day: passed / failed / errored / skipped; pass-rate line on
  a secondary axis; average run duration shown in the tooltip.
- Filters: `days` (7 / 30 / 90), `branch` (free text), `environment` (free
  text), `tz` (defaults to the browser time zone, sent explicitly).

### Tests — `GET /api/v1/projects/{id}/analytics/tests`

- Columns: test (suite / class / name), runs, pass rate, failed, errored,
  avg duration, last status, last seen.
- Controls mapping straight to query params: `sort` (failures / duration /
  name), `search`, `limit` / `offset` pagination (50 per page), `days`.
- Row click navigates to the history view for that `test_key`.

### History — `GET /api/v1/projects/{id}/analytics/tests/{test_key}/history`

- Header: suite / class / name, summary counts and pass rate.
- Executions table: run id, started at, branch, commit (short SHA), 
  environment, status, duration, message (truncated, expandable).
- Filters: `days`, `branch`, `limit`.

### Flaky — `GET /api/v1/projects/{id}/analytics/flaky`

- Table: test, reason badge (`same_commit` = "confirmed", `flips` =
  "suspected"), flips / flip rate, runs, last status, last seen; expandable
  commit list with environments.
- Controls: `window_days` (≤ 30), `min_runs`, `min_flip_rate`.

## Data layer

- One typed API client module (`src/api/`): fetch wrapper that injects the
  bearer token, handles the 401-refresh-retry flow, and parses the gateway's
  JSON error envelope.
- TypeScript interfaces mirror the Pydantic models in
  `platforms/ingestion-service/src/ingestion/schemas/analytics.py`
  (`TrendsOut`, `StatsRowOut`, `HistoryOut`, `FlakyOut`, …).
- TanStack Query keys include project id and all filter values; stale time
  60 s (analytics data changes slowly).

## Error and empty states

- Query error → inline banner in the view with the API's error message and a
  retry button; never a blank page.
- Loading → skeleton rows / chart placeholder.
- Empty data → explicit empty state ("No runs in this window") with the
  active filters named.
- 429 from the gateway → banner asking to retry shortly.

## Testing

- Unit/component: Vitest + React Testing Library with MSW stubbing the
  gateway API — auth flow (login, refresh-on-401, redirect on failed
  refresh), each view renders real-shaped fixture data, filter → query-param
  mapping, pagination.
- Smoke: extend `scripts/` gateway smoke test — dashboard serves `index.html`
  at `/`, static assets load, and the SPA fallback returns `index.html` for a
  deep link.
- CI: new node job — install, lint, typecheck, test, build; the existing
  full-stack smoke job gains the dashboard checks.

## Delivery

- Branch `feat/dashboard-ui`, stacked on `feat/analytics-api` (runtime
  dependency); rebase onto master after PR #14 merges, then its own PR.
- TODO.md: tick "Dashboard UI" under Analytics API; add a follow-ups section
  (SSO buttons, httpOnly refresh cookie, mute/acknowledge, CSV export).
