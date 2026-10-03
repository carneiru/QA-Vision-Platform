# QA Vision Platform Implementation Progress

> Live item-level record. Forward plan: IMPLEMENTATION_PLAN.md. Target
> architecture + adoption triggers: ARCHITECTURE_BLUEPRINT_V1_0.md (read its
> Implementation Status banner first). Current-state spec:
> TECHNICAL_SPECIFICATION.md. New features name the blueprint section they
> serve; TARGET technologies enter only when their trigger fires.

## Completed Tasks

### Phase 1: Foundation Services - AUTHENTICATION SERVICE (COMPLETED)
1. [x] Analyze QA Vision platform requirements and architecture specifications
2. [x] Brainstorm core architecture components and their interactions
3. [x] Design database schema for PostgreSQL based on requirements
4. [x] Plan microservices architecture and communication patterns
5. [x] Design plugin SDK architecture for extensibility
6. [x] Plan deployment strategies for multiple cloud platforms
7. [x] Design AI engine capabilities for test analysis
8. [x] Plan real-time features with WebSockets
9. [x] Design security and compliance features
10. [x] Plan observability and monitoring stack

### Documentation Created
- `docs/superpowers/specs/2026-07-13-qa-vision-architecture-brainstorm.md` - High-level architecture overview
- `docs/superpowers/specs/2026-07-13-qa-vision-database-schema.md` - Complete PostgreSQL schema design
- `docs/superpowers/specs/2026-07-13-qa-vision-microservices.md` - Detailed microservices architecture
- `docs/superpowers/specs/2026-07-13-qa-vision-plugin-sdk.md` - Plugin SDK design for extensibility
- `docs/superpowers/specs/2026-07-13-qa-vision-deployment-strategies.md` - Multi-cloud deployment strategies
- `docs/superpowers/specs/2026-07-13-qa-vision-ai-engine.md` - AI engine capabilities for test analysis
- `docs/superpowers/specs/2026-07-13-qa-vision-realtime-features.md` - WebSocket-based real-time features
- `docs/superpowers/specs/2026-07-13-qa-vision-security-compliance.md` - Security and compliance architecture
- `docs/superpowers/specs/2026-07-13-qa-vision-observability-monitoring.md` - Observability and monitoring stack

### Authentication Service Implementation (Phase 1 - Complete)
11. [x] Set up Auth Service project structure with FastAPI
12. [x] Implement PostgreSQL database models for Users, Sessions, and OAuth Accounts
13. [x] Create Alembic migration system for database schema management
14. [x] Implement secure password hashing with bcrypt (work factor 12)
15. [x] Develop JWT-based access token and refresh token system with rotation
16. [x] Build User Service for CRUD operations and authentication logic
17. [x] Build Auth Service for token management and user authentication
18. [x] Implement SSO framework with Google ID token validation
19. [x] Create RESTful API endpoints for:
    - User registration and email/password authentication
    - Token refresh and secure logout
    - Password reset endpoints (framework ready for SMTP integration)
    - Google SSO authentication (GitHub/Azure placeholders for future implementation)
    - User profile management (self-service and admin endpoints)
20. [x] Implement comprehensive input validation with Pydantic models
21. [x] Add role-based access control (superuser vs regular users)
22. [x] Create Dockerfile and docker-compose for containerized deployment
23. [x] Develop comprehensive test suite (unit and integration tests)
24. [x] Generate interactive API documentation (Swagger UI and ReDoc)
25. [x] Create precise documentation with implementation status clarity
26. [x] Implement environment-based configuration management
27. [x] Add security best practices: CORS protection, SQL injection prevention, input validation
28. [x.1] [x] Implement refresh token rotation to prevent replay attacks
28. [x.2] [x] Add password reset framework (email integration pending SMTP config)
28. [x.3] [x] Establish SSO foundation for future provider implementations

## In Progress / Next Steps

### Phase 2: Organization Service
29. [ ] Design organization and team management data models
30. [ ] Implement organization CRUD operations
31. [ ] Create team management functionality (creation, membership, roles)
32. [ ] Implement role-based access control (RBAC) within organizations
33. [ ] Develop invitation system for team members
34. [ ] Create API endpoints for organization and team management
35. [ ] Implement multi-tenancy data isolation
36. [ ] Write comprehensive test suite
37. [ ] Create API documentation
38. [ ] Add Docker support
39. [ ] Integrate with Auth Service for authentication and authorization

### Phase 3: Project Service
40. [x] Design project management data models
41. [x] Implement project creation, updating, archiving
42. [ ] Create member and permission management within projects *(deferred: access follows organization roles; see the project-service design spec)*
43. [ ] Implement project categorization and tagging system *(not started)*
44. [ ] Develop project templates and cloning functionality *(not started)*
45. [x] Create API endpoints for project management
46. [x] Implement integration with Organization service for access control
47. [x] Write comprehensive test suite
48. [x] Create API documentation
49. [x] Add Docker support
50. [x] Integrate with Auth and Organization services
50.1. [ ] Release the DB session before outbound HTTP calls (members/me, provider verification) so slow upstreams cannot exhaust the connection pool
50.2. [ ] Map only uniqueness violations to 409 in project_service._commit; re-raise other IntegrityErrors

### API Gateway and full stack
- [x] NGINX gateway: routing, per-IP rate limits, self-signed TLS, JSON errors, request ids, JSON access log
- [x] Repository-root docker-compose: one Postgres, db-init, per-service migration jobs, shared SECRET_KEY
- [x] CI: full-stack smoke test through the gateway

### Gateway follow-ups
- [ ] Monitoring dashboards (Prometheus/Grafana) — *Phase 1, "Basic monitoring stack"*
- [ ] Kubernetes ingress; real certificates — *Phase 1 infra, when a cluster exists*
- [x] Service-to-service auth so organization-service can check users in auth-service — auth-service gained `GET /internal/v1/users/{id}` (HTTP Basic, same INTERNAL_API_PASSWORD pattern as project-service's retention API); the superuser `AUTH_SERVICE_TOKEN` is gone from config, compose and docs
- [ ] Shared rate limits in Redis — *when more than one gateway instance runs*
- [ ] JWT validation and per-user limits at the gateway — *when the gateway should reject bad tokens itself*
- [ ] API docs through the gateway — *when a frontend or partner needs browsable docs*
- [ ] WebSockets — *Phase 3, real-time features*

### Ingestion (Phase 2, step 1)
- [x] ingestion-service: project API keys, POST /collect/runs (validation, idempotency, truncation), run read API, Prometheus metrics
- [x] In the root stack and behind the gateway; smoke-tested end to end

### Ingestion follow-ups
- [x] Collector agent MVP (JUnit XML parser, uploader with retry) — `collector/`, see below
- [ ] Queue-based processing for 1000+ events/second — *Phase 2 exit criterion*
- [x] PII detection and redaction; retention policies — masking on ingest, `ingestion-retention` job
- [ ] mTLS between agent and platform
- [ ] Artifacts (screenshots, videos, traces, logs)
- [ ] Per-test history endpoints (test_key is already indexed)
- [x] Revoke a project's API keys when the project is deleted — done by the retention job
- [ ] Re-mask results stored before masking existed (one-off command)
- [ ] Custom masking patterns per project
- [ ] Legal hold and data export before deletion

### Collector agent (Phase 2, step 2)
- [x] `qav-collector upload`: JUnit XML (pytest, Surefire, Playwright, cucumber-js), one run per CI job
- [x] GitHub Actions, GitLab CI and Jenkins detection; retry-safe Idempotency-Keys; parts past 20,000 results / 9 MB
- [x] Retries with backoff and a 2-minute budget; HTTPS and verified TLS; the key never printed
- [x] CI: tests on Python 3.9 and 3.12; end-to-end upload through the gateway in the smoke test
- [x] Tag `collector-v0.1.0` — release workflow builds+verifies on the tag
- [ ] Phase 2 exit criteria: agents on 3 CI platforms in real projects; 10k test executions ingested

### Collector — nice to have
Distribution
- [~] Publish to PyPI: workflow ready (trusted publishing, gated on repo variable PYPI_PUBLISH=true); needs the one-off publisher config on pypi.org (project qav-collector, repo carneiru/QA-Vision-Platform, workflow release-collector.yml, environment pypi)
- [x] Ready-made GitHub Action (`uses: carneiru/QA-Vision-Platform/collector-action@collector-v0.1.0`) and GitLab CI template (`templates/qav-collector.gitlab-ci.yml`) — both install the collector pinned to the tag
- [x] A Jenkins shared-library step — `collector-jenkins/vars/qavCollectorUpload.groovy` (workspace venv install, PEP 668-safe; key via env only). Proven against a real Jenkins LTS in Docker: library loaded from a git repo via JCasC, pipeline build SUCCESS, run stored with ci_provider=jenkins and the build URL
- [x] A Docker image and a single-file (zipapp) build for runners without pip — zipapp (`collector/scripts/build_zipapp.py`, stdlib-only, runs on any Python 3.9+) and `collector/Dockerfile` (python:3.12-slim + git). On every `collector-v*` tag the release workflow uploads sdist+wheel+pyz to a GitHub Release and pushes `ghcr.io/carneiru/qav-collector:<version>` + `:latest` (user-approved public surfaces, 2026-10-03)

Formats
- [x] Cucumber JSON (classic formatter) — scenarios map to the existing result shape (suite=feature, class=uri; background folds in; failed step fails, undefined/pending skip). Rich tags/steps columns still need ingestion fields — deferred until a consumer exists
- [x] Playwright JSON — own reporter format; retries kept as per-attempt results, projectName as suite, timedOut→failed, interrupted→errored. Attachments wait for artifact ingestion (below)
- [x] TestNG XML, NUnit 3 XML, xUnit.net v2 XML, .NET TRX — dispatched on the XML root element (`formats.py`); same result shape, formats mix freely in one upload

Richer data
- [x] Keep each retry attempt as its own result, so flaky tests become visible — Surefire flakyFailure/flakyError/rerunFailure/rerunError expand into per-attempt results (duplicate testcases, pytest-rerunfailures style, already passed through)
- [x] Git metadata: commit author and message (git log -1, best effort), PR number + base branch (GitHub/GitLab env), stored per run and shown on run detail
- [x] Code-change data, not just JUnit: changed files and diff stats per run — collector gitdiff module, ingestion migration 005 + run API, dashboard Changes card. Correlation analytics remain Phase 6 input.
- [x] Components under test: `--component NAME@SHA` (or `QAV_COMPONENTS`) records which repo versions the run exercised (e.g. the product build an E2E suite ran against) — ingestion migration 008 + run API, "Under test" line on run detail. Dormant Phase 6 input; cross-repo correlation and Workspaces stay behind their triggers (ADR-018).
- [x] Test ownership from CODEOWNERS — collector matches each result's `file` (git semantics, last line wins; root/.github/docs locations), ingestion stores `owner` per result (migration 009), run detail shows it
- [ ] Artifact upload (screenshots, videos, traces) — blocked behind the blueprint's MinIO adoption trigger (artifact storage); starts when the artifacts feature is pulled, not before

Reliability and operations
- [x] Keep a failed upload on disk and retry it later — automatic via `--spool` (below); a separate `retry` command adds nothing, the next upload resends first
- [ ] Stream partial results during long runs — needs a long-running watch mode (the collector currently runs after the tests finish; multi-part uploads already flow sequentially). Revisit if a real pipeline shows the need
- [x] `qav-collector check`: verifies URL shape, TLS trust, API key (GET /collect/key names the project) and report parsing, without uploading; exits 2 on the first failure
- [x] Keep-and-retry failed uploads: `--spool DIR` / `QAV_SPOOL` stores undelivered parts (base64 JSON, capped at 100) and the next invocation resends them under their original Idempotency-Key; non-retryable rejections (401/409/4xx/TLS) are dropped, not respooled
- [x] A `.qav.yml` config file — flat keys + string lists, built-in reader (zero dependencies kept for the zipapp); precedence flags > env > file; API key never accepted in the file
- [x] Client certificates (mTLS) — `--client-cert`/`--client-key` (`QAV_CLIENT_CERT`/`QAV_CLIENT_KEY`) load into the TLS context; server-side enforcement is a deployment concern (nginx `ssl_verify_client`), not in the local stack

### Microsoft SSO
- [x] Sign in with Microsoft (Entra ID) ID tokens from an allowlist of tenants; link to an existing account
- [x] Signing-key fetch hardened for Google and Microsoft (timeout, throttled refresh); outages answer 503
- [ ] Personal Microsoft accounts (outlook.com)
- [ ] Map Entra groups / app roles to organization roles
- [ ] SCIM provisioning and deprovisioning
- [ ] GitHub SSO
- [ ] Single sign-out
- [x] MFA for password accounts: TOTP enrollment (QR + otpauth URI), verification on login, recovery codes; SSO sign-ins defer MFA to the identity provider
- [ ] SAML 2.0 sign-in for enterprise IdPs that don't do OIDC (SP-initiated, signed assertions, per-organization IdP metadata); complements the existing Google/Microsoft ID-token flows

### Analytics API (Phase 3, step 1)
- [x] Daily trends in a requested time zone; per-test list, history; flaky detection (same commit + environment, flip rate)
- [x] Summary tables: flaky_daily rollups + analytics-rollup job; window raised to 90 days (90d: 3.9 s from rollups vs 11.3 s live; 14d: 0.8 s)
- [x] Weekly and monthly views — trends bucket=day|week|month (Monday weeks, local calendar), dashboard View select, window up to 365 days
- [x] Branch comparison — per-branch aggregates endpoint + Branches tab with two-branch pass-rate chart
- [x] Mute / acknowledge a flaky test — muted_tests table, mute/unmute endpoints, dashboard controls
- [ ] CSV export
- [x] Dashboard UI — login, project picker, trends, tests, history, flaky (`dashboard/`)

### Dashboard follow-ups
- [x] SSO sign-in buttons (Google, Microsoft) in the login page — rendered only when `VITE_*` client ids are baked at build time; manual verification against a real tenant still pending
- [ ] Refresh token in an httpOnly cookie (needs auth-service support)
- [x] Mute / acknowledge flaky tests
- [x] CSV export buttons on the tests and flaky views (client-side; tests view pages the API at limit=200, capped at 10k rows)
- [x] Branch comparison — per-branch aggregates endpoint + Branches tab with two-branch pass-rate chart
- [x] Organization management UI — `/organizations/:orgId` (members list/remove, invite by email+role, pending invitations with revoke; controls gated on owner/admin via `GET /members/me`; the invite link with the single-use token is shown once, from the 201) and `/invitations/:token` accept page closing the self-service loop; Manage link per organization in the picker. Audit follow-ups landed: member rows carry emails (auth batch internal lookup, best effort), the accept page previews organization+role via authenticated `GET /invitations/{token}` (dead token = unknown token), per-row accessible action names, copy button on the invite link

- [x] Registration in the UI — /register page (full name optional, "check your email" state says where the link lands when SMTP is unconfigured), /verify-email SPA landing that verifies and signs the person in (the emailed link now points there instead of the raw API endpoint), Create account link on the login page
- [x] Create flows in the UI — "New organization" (slug derived from the name, editable, backend pattern enforced) and "New project" (owner/admin only) in the picker; Settings tab per project with API-key management (create shows the full key once with a copy button, list shows prefix/created/last-used, revoke; revoked keys lose the action). Closes the last curl-only step: a team can go from register to first upload entirely in the browser

### Phase 4: Test Management
51. [ ] Design test case and test suite data models
52. [ ] Implement test case creation, versioning, and organization
53. [ ] Create test execution tracking and result storage
54. [ ] Develop test suite management and execution ordering
55. [ ] Implement test case linking and dependencies
56. [ ] Create API endpoints for test management
57. [ ] Implement integration with Project service
58. [ ] Write comprehensive test suite
59. [ ] Create API documentation
60. [ ] Add Docker support
61. [ ] Integrate with Auth, Organization, and Project services

### Phase 5: Analytics & Reporting
62. [ ] Design analytics data models and metrics collection
63. [ ] Implement test execution analytics and trends
64. [ ] Create defect analysis and reporting capabilities
65. [ ] Develop dashboard and visualization framework
66. [ ] Implement scheduled report generation and delivery
67. [ ] Create API endpoints for analytics and reporting
68. [ ] Implement integration with all previous services
69. [ ] Write comprehensive test suite
70. [ ] Create API documentation
71. [ ] Add Docker support
72. [ ] Integrate with all foundation services

### Phase 6: AI Engine (Original Starting Point)
73. [ ] Design AI/ML model architecture for test analysis
74. [ ] Implement test failure pattern recognition
75. [ ] Create intelligent test case generation suggestions
76. [ ] Develop risk-based test prioritization algorithms
77. [ ] Implement predictive analytics for test outcomes
78. [ ] Create natural language processing for test requirements
79. [ ] Develop anomaly detection in test execution patterns
80. [ ] Design model training and retraining pipelines
81. [ ] Create API endpoints for AI-powered insights
82. [ ] Implement integration with Test Management and Analytics services
83. [ ] Write comprehensive test suite
84. [ ] Create API documentation
85. [ ] Add Docker support
86. [ ] Integrate with all platform services

## Next Version (v2) — Backlog

Not scheduled. These move QA Vision from *observing* test runs (the roadmap's scope: a
collector reports results from the customer's own CI) to also *authoring and running*
them. Items marked *(suggested)* were added during review as natural companions to the
requested ones. Each group needs its own design spec before implementation.

### A. Test case management
- [ ] Friendly UI to browse, create and edit test cases (TCs)
- [ ] Create/add labels on TCs; filter and search by label
- [ ] Create suites — static (hand-picked TCs)
- [ ] Dynamic suites defined by a label query, e.g. `smoke AND checkout` *(suggested)*
- [ ] TC versioning: who changed what, and when *(suggested)*
- [ ] Import existing TCs from the repo (Gherkin `.feature` files, JUnit XML) *(suggested)*
- [ ] Link TCs to requirements/tickets (Azure DevOps, Jira) *(suggested)*
- [ ] Bulk actions: label, move, archive many TCs at once *(suggested)*

### B. Test execution
- [ ] Run a single TC, a selection ("bunch"), or a whole suite
- [ ] Re-run only the failures from a previous run
- [ ] First version triggers the customer's CI (GitHub Actions `workflow_dispatch`) rather than running tests on QA Vision's own infrastructure *(suggested — far smaller security surface than executing customer code)*
- [ ] Live run progress and cancel a running job (see `specs/2026-07-13-qa-vision-realtime-features.md`) *(suggested)*
- [ ] Run parameters: target environment, browser/device matrix *(suggested)*
- [ ] Scheduled runs (nightly, per branch) *(suggested)*
- [ ] Flaky-test quarantine: auto-retry policy and a quarantined list excluded from gating *(suggested — builds on Phase 4 flaky detection)*

### C. Results, history and evidence
- [ ] TC run history (pass/fail/duration over time) — already planned in roadmap Phases 2–3
- [ ] View screenshots and screen recordings attached to a run
- [ ] Playwright trace viewer and step-by-step logs per failed TC *(suggested)*
- [ ] Compare two runs side by side *(suggested)*
- [ ] Group failures by error signature, so one broken locator shows as one problem, not forty *(suggested)*
- [ ] Shareable link to a failed run *(suggested)*
- [ ] Failure notifications to Slack/Teams/email *(suggested)*

### D. AI prompt chat
- [ ] Create TCs from a prompt
- [ ] Fix failing TCs from a prompt
- [ ] Every AI change is delivered as a pull request or a reviewable diff, never committed directly *(suggested — keeps a human in the loop)*
- [ ] Explain a failure from its logs and screenshots *(suggested)*
- [ ] Turn manual TC steps into an automated test *(suggested)*
- [ ] Ask questions about test data in plain language ("which tests failed most this week?") — roadmap Phase 6 *(suggested)*
- Note: the roadmap defers "natural language test generation" past year one because predictive ML needs months of collected data. An assistant built on a hosted LLM does not depend on that data, so this group can be scheduled independently of Phase 6.

### E. Repository configuration and secrets
- [ ] Edit configuration files (`*.json`) — restricted to a configured config path only
- [ ] Validate edits against a JSON schema and show a diff before saving; save as a PR *(suggested)*
- [ ] Manage the repo's environment variables (the GitHub `.env`)
- [ ] Store them as GitHub Actions secrets/variables through the GitHub API rather than committing a `.env` file; values write-only and masked in the UI *(suggested — a committed `.env` leaks its secrets to everyone with read access)*
- [ ] Per-environment profiles (dev / staging / prod) *(suggested)*
- [ ] Audit log of every config and secret change *(suggested)*

### F. UX
- [ ] Onboarding wizard: connect a repository, install the collector, first run *(suggested)*
- [ ] Global search across TCs, suites and runs *(suggested)*
- [ ] Personal dashboard: my suites, my recent failures *(suggested)*

### G. Built-in terminal
A terminal in the browser (xterm.js over a WebSocket). An interactive shell is remote code
execution by design, so this ships in three levels, each its own spec, and each level only
after the one before it is proven:
- [ ] **Level 1 — live output console (read-only):** stream a run's stdout/stderr as it happens, with ANSI colours, search, and download. No input. Low risk; reuses the run/job infrastructure from group B
- [ ] **Level 2 — command console (allow-listed):** a terminal-style prompt that only accepts platform commands (`run suite smoke`, `rerun failed`, `git status`, `show config`), each mapped to an API call and bound by the same per-action permissions as the UI. No arbitrary shell
- [ ] **Level 3 — full interactive shell:** a real PTY inside an ephemeral, per-user sandbox container (repo checked out, test toolchain installed), destroyed at session end. Requires: container isolation (gVisor/Firecracker class, no host mounts, no Docker socket), egress restrictions, CPU/memory/time limits, idle timeout, no platform secrets inside the sandbox, session recording to the audit log, and an explicit per-organization opt-in
- Note: Level 3 means running customer code on QA Vision's own infrastructure — the exact surface group B's `workflow_dispatch` approach avoids. Build it only if Levels 1–2 leave a real gap.

### H. Platform prerequisites for v2
These are not features, but groups B, C, D, E and G cannot ship without them:
- [ ] Frontend application (React/TypeScript, per the roadmap tech stack)
- [ ] GitHub App integration — scoped repo access, workflow dispatch, secrets API — instead of personal access tokens
- [ ] Artifact storage for screenshots, videos and traces (S3-compatible; MinIO for local development)
- [ ] Job queue for runs and AI requests (Redis is already in the stack)
- [ ] Secrets management (Vault or cloud equivalent) — brought forward from "prepare for" to required
- [ ] Permissions per action: who may run tests, edit config, manage secrets, accept AI changes

## Completed Documentation (Reference)
All architectural specifications and design documents from the initial brainstorming phase have been completed and serve as the foundation for implementation phases.

## Current Status
**Phase 1 (Authentication Service) is complete and ready for use.** The service provides:
- Secure user authentication with email/password
- JWT-based session management with refresh token rotation
- Foundational SSO capabilities (Google implemented, framework ready for others)
- Password reset framework (requires SMTP configuration for production)
- Comprehensive user management with role-based access
- Full test coverage and API documentation
- Dockerized deployment ready

**Ready to begin Phase 2: Organization Service** which will build upon the Authentication service to provide multi-tenant organization and team management capabilities.
