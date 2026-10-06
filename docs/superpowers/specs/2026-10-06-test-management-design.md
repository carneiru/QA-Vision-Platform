# Test management, first slice: cases, suites, and the link to automated tests

Roadmap Phase 4 ("Test Management") and the v2 backlog section A. Decisions made by the user on
2026-10-06:

- It is a **new service**, as the Blueprint lists Test Management as a capability of its own.
  ADR-022 records why it starts before the "after Phase 2 exit" trigger.
- The first slice is **cases, suites and the link to automated tests**. There is no versioning
  and no import yet.

## Service

- `platforms/test-management-service`, package `src/casebook`, database `testmgmt_db`.
- Same stack and conventions as ingestion-service: FastAPI, SQLAlchemy, Alembic, `qav_shared`.
- Access follows the project role, read from project-service exactly as ingestion does:
  - every project role reads;
  - owner, admin and member edit;
  - a project the caller cannot see is a 404, never a 403.
- Model classes avoid the `Test…` prefix, which pytest would try to collect: `Case`, `Suite`.

## Cases

| Field | Rules |
|---|---|
| `number` | per project, 1, 2, 3…; shown as `TC-12`; never reused |
| `title` | 1–200 characters |
| `description` | optional, up to 10 000 characters (preconditions, context) |
| `steps` | up to 50 `{action, expected}`, each up to 2 000 characters |
| `labels` | up to 20, each 1–40 characters, lower-cased, letters/digits/`-`/`_`/`.` |
| `priority` | `low`, `medium` (default), `high`, `critical` |
| `status` | `draft` (default), `ready`, `archived`; no hard delete, archive instead |
| `automated_test_key` | optional, the 64-hex `test_key` of an automated test; `automated_name` is kept for display |

- The list has search (title, case-insensitive), a label filter (exact; several labels are
  ANDed), status and priority filters, and paging.
- Archived cases are hidden unless asked for.
- `GET /labels` returns every label in use with its count.

## Suites

- A suite has a name (unique per project, 1–100 characters), an optional description, and an
  ordered list of cases.
- `PUT …/suites/{id}/cases` replaces the whole ordered list (case numbers), which covers adding,
  removing and reordering in one request. At most 1 000 cases per suite; unknown numbers are a
  422.
- Deleting a suite never deletes its cases.

## Link to automated results

- The service stores only the `test_key`. The dashboard reads that test's latest status from
  ingestion's existing test history endpoint.
- No call goes from service to service, so neither service depends on the other at runtime.

## API

All under `/api/v1/projects/{project_id}`:

| Method | Path |
|---|---|
| `GET` / `POST` | `/cases` |
| `GET` / `PATCH` | `/cases/{number}` |
| `GET` | `/case-labels` |
| `GET` / `POST` | `/suites` |
| `GET` / `PATCH` / `DELETE` | `/suites/{id}` |
| `PUT` | `/suites/{id}/cases` |

The gateway routes `cases`, `case-labels` and `suites` under a project to the new service.

## Out of scope (later slices)

- Versioning and history.
- JUnit import.
- Dynamic (label-query) suites.
- Links to tickets.
- Bulk actions.
- Running a suite from QA Vision.
