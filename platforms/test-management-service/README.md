# Test Management Service

Written test cases and suites for a project, and the link from each case to the automated test
that implements it.

- Decision: `docs/architecture/adr/ADR-022-test-management-service.md`, and for the import `docs/architecture/adr/ADR-023-gherkin-import.md`
- Design: `docs/superpowers/specs/2026-10-06-test-management-design.md`

## Run

In the platform stack: `docker compose up -d test-management-service`. That also runs
`test-management-migrate` (`alembic upgrade head`) against `testmgmt_db`. The gateway routes
`/api/v1/projects/{id}/(cases|case-labels|suites)` here.

On its own, for the container smoke test: `SECRET_KEY=… docker compose up --build`. It answers on
port 8004, and its database is on 5437.

## Tests

```
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt   # Python 3.11
SECRET_KEY=test .venv/Scripts/python -m pytest -q
```

The integration tests use SQLite. `tests/unit/test_migration.py` runs the real migration.

## API (under `/api/v1/projects/{project_id}`)

Every project role reads. Owner, admin and member edit. A project the caller cannot see answers
404.

| Method | Path | |
|---|---|---|
| `GET` | `/cases?search=&label=&label=&status=&priority=&origin=&folder=&linked=&feature=&ado=&include_archived=&limit=&offset=` | `{total, items}`; archived hidden unless asked; `origin=manual` or `imported`; search also matches the Gherkin text. Filters are ANDed: `folder` (an imported case's `source_path` under that folder, subfolders included), `linked` (true: has an automated test), `feature` (the Gherkin Feature name), `ado` (digits only, else 422; matches the label `ado-<n>`) |
| `POST` | `/cases/search` | the same filters as a JSON body (`labels` is a list and `linked` a boolean; `folder` and `feature` up to 500 characters, `ado` 1-12 digits), plus `test_keys` (up to 20 000 64-hex keys, more is 422) and `keys_mode` (`include` default, or `exclude`, which also keeps cases with no automated test); same response as `GET /cases`; every project role may call it. It exists because a list of keys does not fit in a URL |
| `POST` | `/cases` | `title`, `description`, `steps[{action, expected}]`, `labels`, `priority`, `status`, `automated_test_key`, `automated_name` |
| `POST` | `/cases/import?dry_run=` | `{files:[{path, content}], full, allow_mass_archive, expected_plan_hash}` (`full` and `allow_mass_archive` default to `false`); returns `{plan_hash, summary, items, errors, warnings}`; a dry run writes nothing; accepts an editor's JWT or the CI service token (ADR-024), whose changes are recorded as user 0; a `full` import that would archive over half the live imported cases is 409 `mass_archive` unless `allow_mass_archive` is true |
| `GET` / `PATCH` | `/cases/{number}` | the single read also lists the case's suites; `automated_test_key: null` unlinks |
| `GET` | `/case-labels` | labels in use (archived cases left out), with counts |
| `GET` | `/case-folders` | `[{path, count}]` folders of imported cases; a count includes subfolders and leaves out archived cases |
| `GET` | `/case-features` | `[{feature, count}]` Gherkin Feature names of active imported cases, sorted by feature |
| `GET` / `POST` | `/suites` | name unique per project (409) |
| `GET` / `PATCH` / `DELETE` | `/suites/{id}` | detail lists the cases in order; delete keeps the cases |
| `PUT` | `/suites/{id}/cases` | `{"cases": [3, 1, 2]}` replaces the ordered list |

Limits:

- Title: 200 characters.
- Steps: 50, each up to 2 000 characters.
- Labels: 20, each matching `[A-Za-z0-9._-]{1,40}` and stored lower-case.
- Suite cases: 1 000.
- Search filters: `folder` and `feature` up to 500 characters, `ado` 1-12 digits, `test_keys` up to 20 000.

After deploying migration 003, run a full import once to fill Feature on existing imported cases (every imported case shows as updated in that run).

## Gherkin import

`POST /cases/import` reads `.feature` files, one case per scenario. The repository owns an imported
case: title, steps, labels and Gherkin are read-only (422), the rest stays editable. A scenario that
disappears from an uploaded file is archived. A confirm with `expected_plan_hash` applies exactly the
plan that was previewed, or answers 409 `plan_changed`. See ADR-023.

- `full` defaults to `false`: only the uploaded paths are compared, so the cases of a deleted or
  renamed `.feature` file are not archived or moved (a renamed file's scenarios are created again).
  `full=true` treats the batch as the whole suite: cases of missing files are archived and renamed
  files keep their case numbers. The dashboard sends it when "This is my complete features folder"
  is ticked.
- The response carries `errors` (files skipped for a syntax error) and `warnings` (skipped
  scenarios and tags).
- `summary.mass_archive` tells a dry run whether the guard would refuse the real import.
- The automated link the import sets follows a move; a link picked by hand is never changed.

```
curl -k -X POST "https://localhost:8443/api/v1/projects/1/cases/import?dry_run=true" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"files":[{"path":"tests/features/a.feature","content":"Feature: A\n  Scenario: s\n    Given x\n"}]}'
```

Limits (over any of them is 413, and the message names the setting):

- `IMPORT_MAX_FILES`: files per request, default 2 000.
- `IMPORT_MAX_FILE_BYTES`: one file, default 262 144.
- `IMPORT_MAX_TOTAL_BYTES`: all file content, default 10 485 760.
- `GATEWAY_IMPORT_MAX_BODY`: the gateway's body cap on the import path, default `25m`. Keep it
  above the total plus JSON escaping (about 2.5x is safe).

To raise them, change `.env` and restart the gateway and this service.
