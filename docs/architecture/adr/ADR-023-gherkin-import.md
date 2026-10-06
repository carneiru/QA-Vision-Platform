# ADR-023: Gherkin import: the repository owns imported cases

Status: Accepted (2026-10-06) · Spec: `docs/superpowers/specs/2026-10-06-gherkin-import-design.md`

## Context
The `.feature` files live in the product test repositories, not in QA Vision. Test management
(ADR-022) kept cases written by hand. Teams that already have hundreds of scenarios in Git do not
want to type them again, and do not want two copies that drift apart.

Automated results are identified by `test_key`: for Cucumber JSON, suite = feature name,
class_name = the result's `uri`, name = scenario name. A case can only show its latest result when
its link carries the same key.

On 2026-10-06 the user chose one endpoint for the dashboard upload now and a later
`qav-collector import-features` CI command, with the repository as the source of truth.

## Decision
- **Field ownership.** For an imported case, title, Gherkin text and labels come from the file and
  are read-only in QA Vision (`PATCH` answers 422). Priority, status, description, suites and the
  automated-test link stay editable. A `@priority:` tag sets the priority; without one the case
  keeps its current priority.
- **`source_key`.** `sha256(source_path \0 scenario name)`, unique per project. A case with no
  `source_key` is manual and behaves as before. `source_path` is relative to the repository root and
  `/`-separated.
- **Moves are matched on the Gherkin text.** If an imported case would be archived and a new
  scenario with exactly the same Gherkin text (which includes the scenario name) appears at another
  path in the same batch, the case keeps its number and gets the new path and key. Matching is
  one-to-one; if several candidates match, none is treated as a move.
- **Reactivation.** If the key belongs to an archived case, the case returns to `draft`, and is
  updated if needed. A scenario that disappears is archived, never deleted.
- **`plan_hash`.** The import builds a plan (create, update, unchanged, move, reactivate, archive,
  skip). A dry run returns it with a sha256 over its actions, sorted by path and scenario, so file
  order does not change it. A confirm sends `expected_plan_hash`; if the rebuilt plan differs, it is
  409 `plan_changed` and nothing is written. The user applies exactly what they previewed.
- **One transaction.** A real import applies the whole plan or nothing. Archiving is scoped to the
  uploaded paths, so uploading one folder never archives cases from another. Only `full=true` also
  archives imported cases whose path is not in the batch. Manual cases are never touched, and a file
  that fails to parse never archives its cases. Two imports racing hit the unique `source_key`
  index; the loser gets 409 `import_conflict`.
- **`test_key` lives in `qav_shared`.** It moved out of ingestion's `ingest_service.py`. Ingestion
  and test-management import the same function, and a contract test (a `.feature` fixture and its
  Cucumber JSON) holds the two sides together.
- **A separate gateway body limit.** JSON escaping makes the request larger than the file content,
  so the import path has its own NGINX `location` with `GATEWAY_IMPORT_MAX_BODY` (default `25m`).
  Other routes keep 10 MB. The service limits are `IMPORT_MAX_FILES` (2 000),
  `IMPORT_MAX_FILE_BYTES` (256 KB) and `IMPORT_MAX_TOTAL_BYTES` (10 MB), all read from the
  environment.
- Parsing happens on the server with Cucumber's official parser (`gherkin-official`), one case per
  `Scenario` or `Scenario Outline`, and the Gherkin is kept as text, not converted to steps.

## Consequences
- The automated link only matches Cucumber JSON results whose `uri` equals the imported path. The
  path must be the one the runner reports, from the directory it runs in (hence the path prefix
  option). JUnit results use another identity and will not match.
- An outline whose name has `<placeholders>` links to the name filled from its first Examples row;
  the other rows are found through the test search in the editor.
- An archived case that reappears at a new path becomes a new case, not a move: moves are only
  detected against cases that would be archived in the same batch. The old case stays archived.
- When a case moves, its automated link is kept only when it was set by hand. A link the import
  computed itself is refreshed for the new path.
- A `full=true` import can archive many cases at once. A mass-archive guard (refuse to archive more
  than half of the imported cases without `--allow-mass-archive`) is due with the CLI command.
- API-key access for the CLI and JUnit import are later slices.
- Raising a limit is an `.env` change and a restart of the gateway and the service; no code change.

## Related Decisions
- [ADR-022: Test management is its own service](ADR-022-test-management-service.md)
