# ADR-024: Service tokens for CI imports

Status: Accepted (2026-10-06) · Spec: `docs/superpowers/specs/2026-10-06-ci-feature-import-design.md`

## Context
CI holds only a project API key (`qav_…`). Only ingestion can check it. test-management takes user
JWTs and asks project-service for the caller's role. ADR-022 says services do not call each other,
so test-management cannot ask ingestion whether a key is valid. Yet ADR-023 wants CI to keep
imported cases in sync with `qav-collector import-features`, with no user login in the pipeline.

## Decision
- **A token trade on ingestion.** `POST /api/v1/collect/token`, authenticated with
  `Authorization: Bearer qav_…` through the same check as `POST /api/v1/collect/runs`, returns
  `{"token", "expires_in": 300, "project_id"}`. The token is a JWT signed with the platform's
  `SECRET_KEY`, which every service already shares.
- **Claims.**

  | Claim | Value |
  |---|---|
  | `sub` | `apikey:<api key id>` |
  | `project_id` | the key's project |
  | `organization_id` | the project's organization |
  | `scope` | `cases:import` |
  | `token_type` | `service` |
  | `iat`, `exp` | issued at; `exp = iat + 300 s` |

- **No other route accepts it.** Two layers keep it out of every other route. First, every route
  except the import goes through `get_caller`, which needs a numeric `sub`; `apikey:7` is not a
  number, so a service token is 401 there. Second, `is_access_token`: a token carrying `purpose` or
  `token_type` is never a user session (added by the MFA fix 9ecc1f4). The rule: **any future
  non-session JWT MUST carry `purpose` or `token_type`**. A test pins this, and so does the
  gateway smoke.
- **Related: MFA bypass fix.** The MFA challenge token had a numeric `sub` and was accepted as a
  session by services that only checked `sub`. Commit 9ecc1f4 made `is_access_token` reject any
  token with `purpose` or `token_type` in every service; the service token relies on the same rule.
- **The import route checks scope and project.** `POST /api/v1/projects/{id}/cases/import` takes
  either a user JWT (an editor role from project-service, as before) or a service token with
  `token_type == "service"`, `scope == "cases:import"` and `project_id == {id}`. For a service token
  project-service is not asked. A token for another project is 404 "Project not found", as for a
  project the caller cannot see; a wrong or missing scope is 401.
- **CI is user 0.** Cases a service token creates or changes get `created_by` / `updated_by` = `0`.
- **Short life instead of revocation.** The token lives 5 minutes and is never stored. Nothing
  needs a revocation list: the CLI trades a key for a token on every run.

## Alternatives rejected
- **The gateway `auth_request` with a trusted header** (the gateway checks the key with ingestion
  and adds a header such as `X-Project-Id`). Anyone who can reach test-management directly, on the
  Docker network, could forge the header.
- **Reading ingestion's database from test-management.** It couples two services through a
  database, which ADR-022 avoids.

## Consequences
- One more endpoint on ingestion.
- Revoking an API key stops new tokens at once. A token already issued works for at most 5 more
  minutes.
- Every future service-token route must check `scope` (and the project) itself. Accepting
  `token_type == "service"` alone is never enough.
- The collector skips `node_modules` and refuses patterns that point outside the working directory,
  so a stray pattern cannot upload files from elsewhere on the runner.
- The dashboard does not display `created_by`, so CI's user 0 is not visible yet.

## Related Decisions
- [ADR-022: Test management is its own service](ADR-022-test-management-service.md)
- [ADR-023: Gherkin import: the repository owns imported cases](ADR-023-gherkin-import.md)
