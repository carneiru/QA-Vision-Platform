# CI keeps imported cases in sync: `qav-collector import-features`

This is the slice that follows [Gherkin import](2026-10-06-gherkin-import-design.md) (ADR-023):
"`qav-collector import-features`: CI keeps cases in sync; API-key access to test-management;
mass-archive guard". The user made these decisions on 2026-10-06:

- **Authentication: ingestion trades the project's API key for a short-lived service token.**
  test-management accepts that token on the import route only. No service calls another during an
  import (ADR-022).
- **Only the main branch syncs.** On any other branch the command says it skipped and exits 0.
- **`--full` is on by default.** A guard on the server refuses an import that would archive more
  than half of the imported cases, unless the client allows it explicitly.

## Ingestion: `POST /api/v1/collect/token`

- The gateway already routes `/api/v1/collect` to ingestion, so this needs no gateway change.
- Authentication is `Authorization: Bearer qav_…`, checked by the existing `get_api_key` (hash
  lookup, revoked keys refused, 401 otherwise). `last_used_at` is updated as for uploads.
- The response is `{"token": "<jwt>", "expires_in": 300, "project_id": <id>}`. The JWT is signed with the shared
  `SECRET_KEY` and `ALGORITHM`:

  | Claim | Value |
  |---|---|
  | `sub` | `"apikey:<api key id>"` |
  | `project_id`, `organization_id` | the key's project and organization |
  | `scope` | `"cases:import"` |
  | `token_type` | `"service"` |
  | `exp` | now + 300 s |

- `sub` is deliberately not a number. Every existing service dependency does `int(sub)` and answers
  401, so the token opens no route except the one that accepts it.
- A revoked key gets no new tokens, and a token already issued lives at most 5 minutes.

## test-management

### Import access

- `POST /projects/{id}/cases/import` uses a new dependency, `require_import_access`, which accepts
  either of these:
  - a user JWT, checked exactly as today (an editor role from project-service);
  - a service token with `token_type == "service"`, `scope == "cases:import"` and
    `project_id == {id}`. project-service is not consulted. A wrong project gives 404, as for a
    project the caller cannot see; a wrong or missing scope gives 401.
- Every other route still goes through `get_caller`, which requires a numeric `sub`. A service
  token is 401 there, and a test pins that.
- Cases that a service token creates or changes get `created_by` / `updated_by` = `0`, which means
  "CI". The dashboard shows "CI" for user id 0.

### Mass-archive guard (every client)

- A plan is a **mass archive** when `full=true` and `archived * 2 > live`, where
  `live = archived + unchanged + updated + moved` (the imported cases that are live today). This is
  the same rule the dashboard's warning uses.
- In a dry run the plan is returned as usual, and the summary gains `"mass_archive": true|false`.
- In a real import with a mass archive, the response is 409
  `{"code": "mass_archive", "message": "...", "archived": N, "live": M}` and nothing is written,
  unless the body has `allow_mass_archive: true`.
- The dashboard sends `allow_mass_archive: true` when its mass-archive alert is showing, because a
  person has read it.

## Collector: `qav-collector import-features`

```
qav-collector import-features [PATTERN ...] [--branch NAME] [--no-full] [--allow-mass-archive]
                              [--strict] [--dry-run] [--url URL] [--ca-file FILE]
```

- **Files.**
  - The PATTERNs default to `features:` in `.qav.yml` (a new list key), then to
    `**/*.feature`.
  - Paths are relative to the working directory, which is the repository root in CI, so they equal
    cucumber-js's `uri`. `\` becomes `/`.
  - Files are read as UTF-8; the server strips a byte-order mark.
- **Branch.**
  - `--branch` defaults to `$QAV_IMPORT_BRANCH`, else `master`.
  - When `ci.detect` finds a branch that differs, the command prints
    `skipped: on <branch>; cases sync from <name>` and exits 0.
  - With no CI branch detected (a local run), it proceeds.
- **Flow.**
  1. Trade the API key (`$QAV_API_KEY` only, as for `upload`) for a token at `/api/v1/collect/token`.
  2. POST the files to `/api/v1/projects/{project_id}/cases/import`, with `full` (true unless
     `--no-full`) and `allow_mass_archive` when the flag is given. `project_id` comes from the token
     response.
  3. Print the summary line, up to 5 parse errors and the warning count.
- **`--dry-run`** calls the import with `dry_run=true` and prints every planned action. Nothing is
  written.
- **Exit codes:**
  - 0: imported, skipped, or parse errors without `--strict`.
  - 1: network or TLS failure, 401/403/404, 409 (`mass_archive`, `import_conflict`), 413, or parse
    errors with `--strict`.
  - 2: invalid configuration (no URL, no key, no files matched), as for `check`.
- **Reuse.** The command is a new module, `features.py`. It reuses `upload.make_context`,
  `upload._send` (no redirects, so the Authorization header never leaves the host), `--ca-file`,
  the client certificate options, `ci.detect` and `config_file`.
- **Release.** The collector version becomes `0.3.0`. The dashboard snippet points at the tag
  `collector-v0.3.0`; the user creates and pushes that tag before the dashboard change ships.

## Dashboard

- Settings, "Wire up your CI": every provider's snippet gains a second step,
  `qav-collector import-features "tests/features/**/*.feature"`, with a comment that cases sync
  from `master` only and that `.qav.yml` `features:` can hold the patterns. `COLLECTOR_REF` becomes
  `collector-v0.3.0`.
- The case editor and list show "CI" where `created_by` / `updated_by` is 0.
- The import page sends `allow_mass_archive: true` when its mass-archive alert is showing, and shows
  a 409 `mass_archive` message if the server refuses anyway.

## Testing

- **ingestion:**
  - the token endpoint with a valid key, a revoked key, a malformed key and no key;
  - the claims and the expiry;
  - `last_used_at` is updated.
- **test-management:**
  - a service token imports into its own project; another project is 404;
  - missing or wrong scope is 401; a user token still works;
  - the service token is 401 on `GET /cases`, `PATCH /cases/{n}` and `GET /suites`;
  - `created_by` is 0;
  - mass archive: 409 without the flag (nothing written), 200 with it, `mass_archive` in the dry-run
    summary, and never with `full=false`.
- **collector:**
  - the branch skip (exit 0) and a local run with no branch;
  - `--no-full`, `--allow-mass-archive`, `--strict` and `--dry-run`;
  - `.qav.yml` `features:`;
  - Windows path separators;
  - every exit code;
  - the token exchange, run against a local stub HTTP server as the existing upload tests do.
- **dashboard:**
  - the snippet carries the new step and `collector-v0.3.0`;
  - "CI" shows for user 0;
  - `allow_mass_archive` is sent when the alert shows;
  - the 409 `mass_archive` message.
- **Gateway smoke:** create an API key, trade it for a token, import one feature with the token,
  and check that the token is 401 on `GET /cases`.

## Documentation

- ADR-024 "Service tokens for CI imports": the token trade, its claims, the non-numeric `sub`,
  scope checking, `created_by = 0`, and the alternatives that were rejected (gateway `auth_request`,
  reading ingestion's database).
- ADR-023: the server-side mass-archive guard.
- The collector README covers the command, `.qav.yml` `features:` and the exit codes.
- The service READMEs cover the token endpoint and the import route's two kinds of caller.
- `TODO.md` marks the slice done.

## Out of scope

- Service tokens for any other route.
- Revoking a token before it expires (5 minutes is the bound).
- JUnit XML import.
