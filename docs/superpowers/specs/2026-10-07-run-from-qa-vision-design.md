# Run tests from QA Vision: Play and Stop (v1)

On 2026-10-07 the user asked to run each test from QA Vision, with play, pause and stop controls. They
approved this design for v1:

- **In v1:** Play and Stop.
- **Out of v1:** Pause, and stop followed by a re-run that resumes where the test stopped. These are
  in the future phases below.

Tests keep running in the customer's CI, in this case the OBT repo's GitHub Actions. QA Vision
dispatches a workflow and can cancel it. It never runs test code itself. This is TODO.md section B:
"First version triggers the customer's CI (GitHub Actions `workflow_dispatch`)".

## Decisions

| Topic | Decision |
|---|---|
| GitHub credential | A fine-grained personal access token per project: one repository, "Actions: Read and write" only. It is stored encrypted. A GitHub App comes later (future phase 3). |
| Workflow | A dedicated `qa-vision-run.yml` in the customer repo. Existing workflows are untouched. |
| Who may run or stop | `owner`, `admin` and `member`. `viewer` and `billing_manager` see state only. Any of those three roles can stop a run, and QA Vision records who stopped it. |
| Safety | A confirmation dialog every time, with the "Tests may create real bookings in staging" warning. At most one active QA Vision run per project. Workers are fixed at 1 and retries at 0 in v1. |
| Where it lives | test-management-service. The blueprint puts test case management and test execution in one Execution domain, and this service already owns cases and suites. |
| Selecting a scenario | By file and the raw Gherkin scenario name (`--name "^<name>$"`), not by line, and not by the case title. Lines move when a file is edited, so a stale line would silently run a different scenario. Titles can be truncated or edited. In a Scenario Outline, each `<placeholder>` becomes `.*`, because cucumber-js substitutes example values into the names of the scenarios it runs. |

## test-management-service

### Migration 004

**`cases.scenario_name`** is a new Text column, nullable. The Gherkin import fills it with the raw scenario name, untruncated. The planner treats a different scenario name as an `update`, so cases imported before this change get it on their next import, as `feature_name` did in migration 003. Manual cases keep NULL.

**`ci_targets`** holds one row per project.

| Column | Type | Notes |
|---|---|---|
| `project_id` | Integer, primary key | |
| `provider` | String(20) | `github` (the only value in v1) |
| `repo` | String(200) | `owner/name`, validated by `^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$` |
| `workflow` | String(200) | The file name, validated by `^[A-Za-z0-9._-]{1,100}\.ya?ml$` |
| `ref` | String(255) | A branch name, default `main`. No NUL, no `..`, no leading `-` |
| `token_encrypted` | Text | Fernet ciphertext |
| `token_last4` | String(4) | Shown as "token …a1b2" |
| `token_expires_at` | DateTime(timezone), nullable | From GitHub's `github-authentication-token-expiration` response header when the token is checked. NULL for a token without expiry |
| `updated_by` | Integer | |
| `updated_at` | DateTime(timezone) | |

**`run_requests`** holds one row per Play.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, primary key | |
| `project_id` | Integer, indexed | |
| `requested_by` | Integer | |
| `requested_at` | DateTime(timezone) | |
| `selection` | JSON | `[{"case_number", "path", "name"}]` |
| `suite_id` | Integer, nullable | Set when a suite was run |
| `status` | String(20) | `queued`, `running`, `completed`, `cancelling`, `cancelled`, `failed_to_start` |
| `conclusion` | String(30), nullable | The GitHub conclusion: `success`, `failure`, `cancelled`, `timed_out`, … |
| `github_run_id` | BigInteger, nullable | |
| `github_run_url` | Text, nullable | |
| `stopped_by` | Integer, nullable | |
| `stopped_at` | DateTime(timezone), nullable | |
| `error` | String(500), nullable | |
| `checked_at` | DateTime(timezone), nullable | When GitHub was last polled |

A partial unique index on `project_id`, where `status` is `queued`, `running` or `cancelling`,
enforces one active run per project.

**`ci_target_events`** is the audit trail for the credential.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, primary key | |
| `project_id` | Integer, indexed | |
| `user_id` | Integer | |
| `action` | String(20) | `created`, `updated`, `token_replaced` or `deleted` |
| `at` | DateTime(timezone) | |

Run starts and stops are already recorded in `run_requests` (`requested_by`, `stopped_by`). The
events table is never deleted when the target is deleted.

### Token encryption

- **Key:** the token is encrypted with Fernet from the `cryptography` package (a new dependency).
  The key comes from the `TM_SECRETS_KEY` environment variable.
- **Without the key:**
  - `PUT /ci-target` returns 503 with "Running tests from QA Vision is not configured on this
    server".
  - `GET` reports `{"available": false}`.
- **Never in clear:** no response, log line or error message carries the token. Responses show
  `token_last4` only.

### Endpoints

All endpoints sit under `/api/v1/projects/{id}/`. They use the service's existing auth and project
role lookup.

| Method and path | Roles | Behaviour |
|---|---|---|
| `GET ci-target` | every project role | `{available, configured, provider, repo, workflow, ref, token_last4, updated_at}` |
| `PUT ci-target` | `owner`, `admin` | Body `{repo, workflow, ref, token?}`. The token is required on the first save. See "Saving a target" below. |
| `DELETE ci-target` | `owner`, `admin` | Removes the target, including the token. Returns 409 while a run is active. |
| `POST run-requests` | `owner`, `admin`, `member` | Body `{case_numbers: [1..200]}` or `{suite_id}`. See "Starting a run" below. |
| `GET run-requests?limit=&offset=` | every project role | Newest first. Active rows are refreshed as described in "Polling" below. |
| `GET run-requests/{rid}` | every project role | Same refresh rule. |
| `POST run-requests/{rid}/stop` | `owner`, `admin`, `member` | Calls `POST /repos/{repo}/actions/runs/{run_id}/cancel`. Sets `cancelling`, `stopped_by` and `stopped_at`. Returns 409 if the run is already finished. A `queued` request that has no `github_run_id` yet is marked `cancelled` locally, and is cancelled on GitHub once it is matched. |

**Saving a target:**
- The service checks the token with GitHub: `GET /repos/{repo}` and
  `GET /repos/{repo}/actions/workflows/{workflow}`.
- If a check fails, it answers 422 with a specific message:
  - 401: "token invalid or expired";
  - 403: "token has no Actions access to this repository";
  - 404: "repository or workflow not found. The workflow file must exist on the repository's
    default branch", because GitHub accepts `workflow_dispatch` only for a workflow that is on the
    default branch.
- A successful save stores `token_expires_at` and writes a `ci_target_events` row.

**Starting a run:**
- Each case becomes `{path: source_path, name: scenario_name}`.
- The service rejects with 422, and lists the offending case numbers, when:
  - a case is manual (it has no `source_path`);
  - a case has no `scenario_name` yet. The message says "re-import the .feature files first";
  - a case is archived;
  - a case is unknown;
  - the selection is empty after a suite expands.
- Before it answers 409 for an already active run, it refreshes that run from GitHub, ignoring the
  5-second throttle. It answers 409 only if the run is still active. Otherwise the refresh closes
  it and the new run starts. Without this, a run that finished while nobody had the page open would
  block every later Play.
- It returns 412 when no target is configured.
- It inserts the row as `queued`, then calls
  `POST /repos/{repo}/actions/workflows/{workflow}/dispatches` with
  `{ref, inputs: {paths, names, request_id}}`:
  - `paths`: the space-separated, deduplicated files;
  - `names`: a JSON array of scenario names;
  - `request_id`: the row id.
- If the dispatch fails, the row becomes `failed_to_start` with the error.

### Polling

There is no background worker. A `GET` of an active request refreshes it from GitHub when
`checked_at` is older than 5 seconds.

- **Matching the run:** when `github_run_id` is null, the service lists the workflow's runs
  (`event=workflow_dispatch`, `created>=` the request time minus 1 minute). It picks the run whose
  `display_title` is `QA Vision #<id>`.
- **Updating the status:**
  - GitHub's `queued`, `waiting`, `requested` and `pending` map to `queued`;
  - `in_progress` maps to `running`;
  - `completed` maps to `completed` or, when the conclusion is `cancelled`, to `cancelled`. The
    `conclusion` is stored as well.
- **Run never seen:** if no run has been matched 2 minutes after the request, the row becomes
  `failed_to_start` with "The workflow did not start". This frees the one-active-run limit.

### GitHub client

- It uses `httpx` with a 10-second timeout and calls `https://api.github.com` only, never following
  redirects.
- It sends the headers `Accept: application/vnd.github+json` and
  `X-GitHub-Api-Version: 2022-11-28`.
- The repo and workflow are validated by regex before they are put into a URL.
- A rate limit (403 or 429 with `x-ratelimit-remaining: 0`) is reported as "GitHub rate limit,
  try again in N s". The request does not change state.

## Gateway

The test-management location regex gains `ci-target|run-requests`.

## Dashboard

### Project Settings: "Run from QA Vision"

This section is visible to `owner` and `admin`.

- **Fields:**
  - repository (`owner/name`);
  - workflow file (default `qa-vision-run.yml`);
  - branch (default `main`);
  - token, as a password field. When a token is already stored, a "Replace token" button shows
    instead.
- **Save:** saving shows "Connected: owner/name · token …a1b2 · expires 12 Mar 2027", or the
  service's specific error next to the form.
- **Audit line:** "Last changed by <name> on <date>", from `ci_target_events`.
- **Expiry warning:** from 14 days before `token_expires_at`, owners and admins see a warning,
  "The GitHub token expires on <date>. Replace it in Settings", in this section and in the run
  panel. After expiry, Play is disabled with "GitHub token expired".
- **Disconnect:** a "Disconnect" button removes the target after a confirmation.
- **Help block:**
  - how to create the token: fine-grained, only this repository, "Actions: Read and write";
  - the `qa-vision-run.yml` content, ready to copy;
  - the repository secret `QAV_API_KEY` and variable `QAV_URL` the workflow needs.
- **Server not configured:** when `available` is false, the section says so and shows no form.

### Play

- **Places:**
  - "Run" on the case detail, for imported cases only;
  - a checkbox per row on the Cases list, with a "Run selected (n)" bar. At most 200 cases can be
    selected. Manual cases have no checkbox;
  - "Run suite" on a suite.
- **Confirmation dialog:**
  - the cases, up to 10 and then "+n more";
  - `repo` @ `ref`;
  - the warning "Tests may create real bookings in staging";
  - "Run" and "Cancel" buttons.
- **Disabled Play:** Play is disabled, with the reason shown as text, when:
  - no target is configured ("Configure in Settings", linked);
  - the user is a viewer ("Viewers can't run tests");
  - a run is active ("A run is in progress").

### Run panel

The panel shows at the top of Cases, and on a case detail while that case is in the active
request.

- **States:**
  - "Queued";
  - "Running · n tests · started by <name> · <elapsed>";
  - "Passed", "Failed" or "Cancelled", from the conclusion;
  - "Didn't start: <error>".
- **Refresh:** the panel polls every 5 seconds while the request is active, and stops when it ends.
- **Link:** "View in GitHub" opens `github_run_url`.
- **Stop:**
  - Stop asks for confirmation ("Stop this run?"), then shows "Stopping…".
  - The panel ends on "Stopped by <name>".
- **After completion:**
  - The panel links to the QA Vision test run whose CI URL equals `github_run_url`, compared
    case-insensitively, because GitHub may return `owner/repo` with different capitals.
  - Until that run arrives, it shows "Waiting for results…".
  - After 5 minutes with no results, it shows "Results not received: check the QA Vision upload
    step".
- **Accessibility:** the panel is a `role="status"` region. Every control has a label and works by
  keyboard. Icons are SVG and colours come from tokens.

### Runs page: "Requested runs" tab

The tab lists date, requested by, number of cases, status, stopped by, and links to GitHub and to
the test run.

## OBT repository: `qa-vision-run.yml`

QA Vision delivers this file as a patch, and the user applies it, because the repo is company code.

- **Trigger:** `on: workflow_dispatch` with the inputs `paths`, `names` and `request_id`, all
  strings.
- **Run name:** `run-name: "QA Vision #${{ inputs.request_id }}"`.
- **Job:**
  - `concurrency: qa-vision-run`, with `cancel-in-progress: false`;
  - `ubuntu-24.04`;
  - runs only on the configured branch.
- **Steps:** checkout, then `./.github/actions/setup-test-env`, then a Node script.
- **The Node script:**
  - receives the inputs only through environment variables, never through `${{ }}` inside `run:`;
  - validates each path against `^tests/features/[\w./ -]+\.feature$` and rejects `..`;
  - parses `names` as a JSON array of strings;
  - escapes each name for a regular expression, then turns each escaped `<placeholder>` into `.*`;
  - runs `npx cucumber-js <paths> --name "^<name>$" … --profile ci --parallel 1 --retry 0` through
    `spawn` with an argument array.
- **After the tests, with `if: always()`:**
  - `collector-action` uploads `test-results/cucumber-report.json` to `vars.QAV_URL` with
    `secrets.QAV_API_KEY`;
  - the Cucumber HTML report is uploaded as an artifact.
- **Zero scenarios:** when the selection matched no scenario, the job writes a warning to its
  summary. This happens when a scenario was renamed without a re-import.

## Testing

### test-management (pytest)

GitHub is stubbed in these tests; nothing calls the real API.

- **Encryption:** a round trip works; no response carries the token; without `TM_SECRETS_KEY`, `PUT`
  returns 503 and `GET` reports `available: false`.
- **`PUT ci-target`:** OK, 401, 403 and 404 from GitHub; regex rejection of bad `repo`, `workflow`
  and `ref`; the roles; `token_expires_at` stored from the header, and NULL without it; a
  `ci_target_events` row for each create, update, token replacement and delete.
- **Stale active run:** a run that finished on GitHub while nobody polled does not block a new
  Play; one that is still running does (409).
- **Import:** the import fills `scenario_name`, a re-import fills it on old cases, and a manual case keeps NULL.
- **`POST run-requests`:**
  - cases are translated to files and names, and a suite expands;
  - a case without `scenario_name` is rejected with the re-import message;
  - manual, archived and unknown cases are rejected with their numbers;
  - more than 200 cases gives 422;
  - an active run gives 409, and a missing target gives 412;
  - a `viewer` gets 403;
  - a failed dispatch gives `failed_to_start`;
  - the dispatch body is exact.
- **Polling:**
  - matching by `display_title`;
  - the status mapping;
  - the 5-second throttle;
  - the 2-minute `failed_to_start`.
- **Stop:**
  - the cancel call is made, and `stopped_by` is recorded;
  - a finished run gives 409;
  - a queued request with no run id is cancelled locally.
- **Migration 004:** up and down. The partial unique index blocks a second active run.

### Dashboard (vitest)

- the Settings section: save, specific error, replace token, disconnect, server not configured;
- Play from the case, from a selection and from a suite;
- the confirmation dialog;
- each reason for a disabled Play;
- the panel's states, Stop, "Waiting for results" and its 5-minute message;
- the Requested runs tab.

### Other

- **Gateway smoke:** `GET ci-target` and `GET run-requests` through the gateway.
- **End to end:** after the user applies the OBT patch and saves a token, one OBT scenario is run
  from the dashboard through the tunnel. The run reaches "Passed" or "Failed", and its results
  appear in Last runs.

## Documentation

- **test-management README:** the endpoints, `TM_SECRETS_KEY`, and that `qa-vision-run.yml` must be
  on the default branch before the first Play.
- **`.env.example`:** gains `TM_SECRETS_KEY`, with how to generate it.
- **DESIGN.md:** the run panel and the Play and Stop controls.
- **TODO.md section B:** v1 marked done, and the future phases listed.
- **Security note** in the README: what the token can do, who can trigger a run, and how to revoke
  the token.

## Future phases (not in v1)

1. **Pause and Resume.**
   - A cucumber `BeforeStep` hook in the customer repo asks QA Vision whether to continue. Pause
     holds before the next step, with the browser still open.
   - A screenshot taken on pause is sent to QA Vision.
   - A pause has a limit (for example 15 minutes) and then stops automatically.
   - The hook fails open: if QA Vision is unreachable, the test runs on.
2. **Stop followed by a resuming re-run**, built on Pause, plus "Re-run failures" of a finished run.
3. **A GitHub App** instead of the personal token: short-lived installation tokens owned by no
   single person. This is the TODO item "connect repository".
4. **Run parameters** (environment, workers, retries), scheduled runs, and more CI providers
   (GitLab, Azure Pipelines).
5. **A dedicated `execution-service`** once execution outgrows test-management.

## Out of scope

- Running tests on QA Vision's own infrastructure.
- Showing live step-by-step progress inside a run. The run panel shows the GitHub job state only.
