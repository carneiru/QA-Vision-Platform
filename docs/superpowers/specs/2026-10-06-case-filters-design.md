# Test cases: more filters, a folder tree, and searchable dropdowns

The Cases list now holds real suites. The OBT import added 1 042 cases from 991 `.feature` files
spread over about 40 folders. The current filters (search, label, status, priority, origin) are not
enough to find a case in that. The user made these decisions on 2026-10-06:

- **New filters:**
  - a **folder tree** built from imported cases' `source_path`;
  - **automation link** (linked / not linked);
  - **latest result** (passed / failed / skipped / never ran);
  - **Feature** (the Gherkin `Feature:` name);
  - **Azure DevOps item** (`@ado:NNN`).
- **The latest-result filter is joined in the dashboard (option A).** Ingestion returns the test
  keys whose latest result has a status; the dashboard passes them to test-management's case
  search. Paging stays on the server, and no service calls another (ADR-022).
- **A dropdown with more than 15 options has a search box at the top of its list.** This applies
  to every filter dropdown in the dashboard, not only Cases.
- **The tree is a left panel** beside the list on desktop, and a drawer on small screens.

## test-management

### Migration 003

- `cases.feature_name` String(500), nullable.
- The import fills it from `ParsedScenario.feature_name`. The planner's `_differs` treats a
  different feature name as an `update`, so cases imported before this change get it on their next
  import. Manual cases keep NULL.

### List filters

`GET /cases` gains these query parameters. All filters are ANDed with the existing ones.

| Parameter | Meaning |
|---|---|
| `folder` | `source_path` starts with `<folder>/`, so it includes subfolders. No trailing slash. A path that is not a known folder matches nothing. |
| `linked` | `true`: `automated_test_key` is set. `false`: it is NULL. |
| `feature` | `feature_name` equals the value exactly. |
| `ado` | digits only (otherwise 422); the case has the label `ado-<value>`. |

`POST /cases/search` accepts the same filters as a JSON body (`search`, `labels`, `status`,
`priority`, `origin`, `include_archived`, `folder`, `linked`, `feature`, `ado`, `limit`, `offset`)
plus:

- `test_keys`: a list of up to 20 000 64-hex keys;
- `keys_mode`: `include` or `exclude`.

The modes mean:

- `include`: only cases whose `automated_test_key` is in the list.
- `exclude`: cases whose `automated_test_key` is NULL or not in the list.

The response has the same shape as `GET /cases`. Roles are as for `GET /cases`: every project
role reads.

### Facets

- `GET /case-folders` returns `[{path, count}]` for every folder that holds an active imported
  case, directly or below it. `count` includes subfolders. Archived cases are left out, as in
  `GET /case-labels`.
- `GET /case-features` returns `[{feature, count}]` for active imported cases, sorted by feature.

## ingestion

`GET /projects/{id}/analytics/latest-keys?status=passed|failed|skipped|any&branch=` returns
`{"keys": [...]}`.

- For each test of the project, it finds the latest result (most recent run), optionally only from
  runs on `branch`.
- It returns the keys whose latest status equals `status`. `any` means the test has at least one
  result.
- `errored` results count as `failed`, as they do in the rest of analytics.
- Every project role reads.

It sits under `/analytics/`, so the gateway already routes it and it cannot clash with
`/tests/{test_key}`.

## Gateway

The test-management location regex gains `case-folders|case-features`. The current regex only
routes `cases|case-labels|suites`, so `/case-folders` would otherwise reach project-service.

## Dashboard

### `FilterSelect` (`components/FilterSelect.tsx`)

- **15 options or fewer:** a native `<select>`, exactly as today.
- **More than 15:** an accessible combobox, following the WAI-ARIA combobox pattern with a listbox
  popup.
  - Opening the list puts focus in a search field at its top. The search matches anywhere in an
    option's text, ignoring case and accents.
  - A line reads "x of y". With no match, the list says "No matches".
  - Keyboard: ↑ and ↓ move, Enter picks, Esc closes and returns focus to the trigger, and Home and
    End jump to the ends.
  - The trigger shows the selected value and a clear button.
  - It looks like the native select, in light and dark mode, and at 375px.
- **Used for** every filter dropdown:
  - Cases: label, feature, Azure DevOps item, status, priority, origin, link, result;
  - Runs: status, environment, CI, branch, author, and the other select filters on that page;
  - the case editor's automated-test picker, if it is a select. If it is a search box, it stays as
    it is.

### `FolderTree` (`components/FolderTree.tsx`)

- **Building the tree:** it is built from `GET /case-folders`.
  - The root is "All cases" with the total.
  - Common leading folders that hold a single child are collapsed into one node, so
    `tests/features` shows as `features` when everything sits under it.
- **Behaviour:**
  - Each node shows its name and count. Clicking a node sets `folder`; clicking the selected node
    again clears it.
  - It is an ARIA `tree`. ↑ and ↓ move, → expands, ← collapses or goes to the parent, and Enter or
    Space selects.
  - The path to the selected folder is expanded when the page loads.
- **Layout:**
  - The panel can be hidden. The choice is kept in `localStorage`, wrapped in try/catch.
  - Under 900px the panel is replaced by a "Folder: <name> ▾" button that opens the tree in a
    drawer. The drawer closes on selection and on Esc.
- Manual cases have no folder and appear only under "All cases".

### Cases page

- **Filters:** search, status, priority, origin, link, latest result, feature, Azure DevOps item
  and label, plus the tree's folder.
  - Every filter lives in the URL. Changing one resets to page 1.
  - "Clear filters" resets them all.
- **Azure DevOps options:** the ADO dropdown lists the work items found in the project's
  `ado-<n>` labels.
- **Latest result:** the page calls `latest-keys` and then `POST /cases/search`.
  - For passed, failed and skipped it uses `include`.
  - For "never ran" it asks for `status=any` and uses `exclude`.
  - With no result filter, the page keeps using `GET /cases`.
  - If `latest-keys` fails, a banner says the result filter cannot be applied right now, and the
    list shows the other filters' results.

## Testing

- **test-management (pytest):**
  - each new filter on `GET /cases`, including folder prefix boundaries: `a/b` does not match
    `a/bc/x.feature`;
  - `linked`, `feature`, and `ado` (including the 422 for a non-numeric value);
  - `/cases/search` with `include` and `exclude`, including that `exclude` keeps unlinked cases,
    and the key limit (422 above 20 000);
  - `/case-folders`: counts include subfolders and leave out archived cases;
  - `/case-features`;
  - migration 003 up and down;
  - import fills `feature_name`, and a re-import fills it on old cases.
- **ingestion (pytest):** `latest-keys` for each status, with the latest result winning over older
  ones, with `branch`, with `errored` counting as failed, and with roles.
- **dashboard (vitest):**
  - `FilterSelect`: native select at 15 options, combobox at 16; search, the count, "No matches",
    keyboard, and clear;
  - `FolderTree`: counts, prefix collapse, select and clear, keyboard, and the drawer under 900px;
  - Cases: each filter reaches the API and the URL; both requests for the result filter
    (`include`, and `exclude` for "never ran"); the banner when `latest-keys` fails; Clear filters;
  - Runs: filters still work through `FilterSelect`.
- **Gateway smoke:** `GET /case-folders`, `POST /cases/search` and `GET /analytics/latest-keys`
  through the gateway.
- Before push, run every CI step: the dashboard's lint, typecheck, tests and build, and each
  service's pytest.

## Documentation

- The test-management README covers the new filters, `/cases/search` and the facets.
- The ingestion README covers `latest-keys`.
- `TODO.md` gets an entry.
- `DESIGN.md` (the dashboard's design notes) records the rule that more than 15 options means a
  searchable dropdown, if `DESIGN.md` holds component rules.

## Out of scope

- Saving filter combinations as named views.
- Filtering by latest result on a specific environment.
- Multi-select within one filter, for example two labels at once. Label filters are already ANDed
  through repeated `label` parameters in the API, but the UI keeps one label.
