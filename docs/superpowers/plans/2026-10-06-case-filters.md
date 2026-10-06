# Case Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Cases list gets more filters:
- a folder tree built from `source_path`;
- automation link;
- latest result;
- Gherkin Feature;
- Azure DevOps item.

Every filter dropdown with more than 15 options gets a search box at the top of its list.

**Architecture:**
- **test-management** gains:
  - a `feature_name` column (migration 003), filled by the import;
  - new list filters;
  - `POST /cases/search`, which takes a list of test keys for the result filter;
  - two facet endpoints, `/case-folders` and `/case-features`.
- **ingestion** gains `GET /analytics/latest-keys`.
- **The dashboard** joins the two services: for a result filter it asks ingestion for keys, then searches cases with them.
- **New components:**
  - `FilterSelect`: a native select with 15 options or fewer, an accessible searchable combobox above 15;
  - `FolderTree`: an ARIA tree.

**Tech Stack:** FastAPI, SQLAlchemy and Alembic, pytest; React + TS, TanStack Query, vitest + msw; NGINX.

**Spec:** `docs/superpowers/specs/2026-10-06-case-filters-design.md`

## Global Constraints

- `GET /cases` gains `folder` (≤500 chars, no NUL), `linked` (bool), `feature` (≤500, no NUL) and `ado` (`^[0-9]{1,12}$`, else 422). These are ANDed with the existing filters.
  - `folder` matches `source_path LIKE '<escaped folder>/%'`.
  - `ado` matches the label `ado-<n>`.
- `POST /cases/search` takes the same filters as a JSON body, plus `test_keys` (≤20 000 64-hex keys; above that, 422) and `keys_mode` (`include` | `exclude`, default `include`).
  - `exclude` keeps cases whose `automated_test_key` is NULL.
  - The response has the same shape as `GET /cases`, and every project role can read it.
- `GET /case-folders` returns `[{path, count}]`. Counts include subfolders and leave out archived cases.
- `GET /case-features` returns `[{feature, count}]`, for active imported cases only, sorted by feature.
- Migration `003` adds `cases.feature_name` String(500), nullable. The import fills it, and a differing value is an `update`.
- Ingestion: `GET /api/v1/projects/{id}/analytics/latest-keys?status=passed|failed|skipped|any&branch=` returns `{"keys": [...]}`.
  - "Latest" means the most recent run (`started_at` desc, then `Run.id` desc).
  - `failed` includes `errored`.
  - `any` means the test has at least one result.
  - Every project role can read it.
- The gateway's test-management regex becomes `(cases|case-labels|case-folders|case-features|suites)`.
- `FilterSelect` is a native `<select>` with ≤15 options and a combobox with >15.
  - The combobox has a search field at the top of its list. Search matches anywhere in the text, ignoring case and accents.
  - It shows an "x of y" count and "No matches".
  - Keyboard: ↑/↓, Enter, Esc (returns focus to the trigger), Home/End.
  - It has a clear button.
- `FolderTree`:
  - Its root is "All cases".
  - Leading single-child folders collapse (`tests/features` becomes `features`).
  - It is an ARIA tree: ↑/↓ move, → expands, ← collapses or goes to the parent, Enter or Space selects. Clicking the selected node clears it.
  - The panel can be hidden (kept in `localStorage` under `qav.cases.foldersHidden`, inside try/catch).
  - Under 900px it is a "Folder: <name> ▾" button that opens a drawer, which closes on selection or Esc.
- All Cases filters live in the URL, under the keys `q`, `label`, `status`, `priority`, `origin`, `folder`, `linked`, `result`, `feature`, `ado`.
  - `result` is `passed|failed|skipped|never`.
  - A "Clear filters" button resets them.
  - If `latest-keys` fails, a banner says "Latest result filter unavailable right now", and the list shows the other filters' results.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Work on master and never push. Commit only your own paths: `git add <files> && git commit -m "<msg>" -- <files>`.
- Never run two pytest processes in the same service at once (they share a SQLite test DB).
- Dashboard: invoke the `ui-ux-pro-max` skill before UI edits. Before reporting done, run `npm run lint`, `npm run typecheck`, `npx vitest run` and `npm run build`.

## Review Focus

1. **Folder names containing `_` or `%`.** `flights_amadeus` must not act as a LIKE wildcard: `_escape_like` is required. Pinned in Task 2 (`test_folder_names_are_matched_literally`).
2. **`folder=tests/features/hotel` must not match `tests/features/hotels/…`.** Pinned in Task 2 (`test_folder_matches_whole_segments`).
3. **"Never ran" with an empty key list** (no results ever uploaded) must return every case, linked or not. Pinned in Task 2 (`test_exclude_with_no_keys_returns_everything`).
4. **Latest result where an older run failed and the newest passed** must count as passed only. Pinned in Task 3 (`test_only_the_latest_result_counts`).
5. **A combobox inside the Cases `<form>`.** Pressing Enter in its search field must pick an option, not submit the form. Pinned in Task 4 (`enter in the search field picks and does not submit the form`).

---

### Task 1: `feature_name` on cases (migration 003, import)

**Files:**
- Create: `platforms/test-management-service/alembic/versions/003_case_feature_name.py`
- Modify: `src/casebook/models/case.py`, `src/casebook/gherkin_import/plan.py` (`Existing`, `_differs`), `src/casebook/service/import_service.py` (`load_existing`, `_content`, the create branch), `src/casebook/schemas/case.py` (`CaseOut`), `src/casebook/service/case_service.py` (`out`)
- Test: `tests/unit/test_import_plan.py`, `tests/unit/test_migration.py`

All paths are relative to `platforms/test-management-service`.

**Interfaces:**
- Produces: `Case.feature_name: str|None`, `Existing.feature_name: Optional[str] = None`, `CaseOut.feature_name: Optional[str] = None`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/unit/test_import_plan.py`, reusing its `run(db, files, full=False)` helper, `A` and `FEATURE`:

```python
def test_import_records_the_feature_name(db):
    run(db, [(A, FEATURE)])
    assert {c.feature_name for c in db.query(Case).all()} == {"A"}


def test_a_case_imported_before_feature_names_gets_one_on_the_next_import(db):
    run(db, [(A, FEATURE)])
    for case in db.query(Case).all():
        case.feature_name = None
    db.commit()
    plan = run(db, [(A, FEATURE)])
    assert plan.summary()["updated"] == 2
    assert {c.feature_name for c in db.query(Case).all()} == {"A"}
    assert {i.action for i in import_service.plan_import(db, 1, [(A, FEATURE)], False).items} == {"unchanged"}
```

Append to `tests/unit/test_migration.py`:

```python
def test_downgrade_to_002_drops_feature_name(tmp_path):
    url = f"sqlite:///{(tmp_path / 'down3.db').as_posix()}"
    cfg = Config()
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "002")
    engine = create_engine(url)
    try:
        assert "feature_name" not in {c["name"] for c in inspect(engine).get_columns("cases")}
    finally:
        engine.dispose()
```

- [ ] **Step 2: Run the tests and check they fail.** From `platforms/test-management-service`: `SECRET_KEY=test .venv/Scripts/python -m pytest -q tests/unit/test_import_plan.py tests/unit/test_migration.py`. Expected: FAIL (`Case` has no `feature_name`).

- [ ] **Step 3: Implement**

`alembic/versions/003_case_feature_name.py`:

```python
"""cases.feature_name: the Gherkin Feature an imported case came from (case filters)

Revision ID: 003
Revises: 002
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("feature_name", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("feature_name")
```

Changes elsewhere:
- **models/case.py:** after `gherkin`, add `feature_name = Column(String(500), nullable=True)  # Gherkin "Feature:" of an imported case`.
- **plan.py:**
  - `Existing` gains a last field, `feature_name: Optional[str] = None`.
  - In `_differs`, add `or case.feature_name != scenario.feature_name[:500]` inside the returned expression.
- **import_service.py:**
  - `load_existing` passes `feature_name=r.feature_name`.
  - `_content` sets `row.feature_name = scenario.feature_name[:500]`.
  - The create branch's `Case(...)` gains `feature_name=s.feature_name[:500]`.
- **schemas/case.py:** `CaseOut` gains `feature_name: Optional[str] = None`.
- **case_service.out():** adds `"feature_name": row.feature_name`.

- [ ] **Step 4: Run the whole service suite and check it passes.** Run `SECRET_KEY=test .venv/Scripts/python -m pytest -q`. `test_migration_columns_match_models` must pass with the new column.

- [ ] **Step 5: Commit** — `feat(test-management): cases remember their Gherkin Feature (migration 003)`.

---

### Task 2: Case filters, `/cases/search` and facets

**Files:**
- Modify: `src/casebook/service/case_service.py` (`list_cases`, plus new `folder_counts`, `feature_counts`)
- Modify: `src/casebook/schemas/case.py` (new `CaseSearch`, `FolderCount`, `FeatureCount`)
- Modify: `src/casebook/api/v1/endpoints/cases.py` (GET params, `POST /search`, `folders_router`, `features_router`)
- Modify: `src/casebook/api/v1/api.py` (mount the two routers)
- Test: `tests/integration/test_case_filters.py` (new)

All paths are relative to `platforms/test-management-service`.

**Interfaces:**
- Consumes: `Case.feature_name` (Task 1).
- Produces:
  - `GET /cases?folder=&linked=&feature=&ado=`
  - `POST /cases/search` (body `CaseSearch`) → `CaseList`
  - `GET /case-folders` → `[{path, count}]`
  - `GET /case-features` → `[{feature, count}]`

- [ ] **Step 1: Write the failing tests** in `tests/integration/test_case_filters.py`:

```python
"""Case list filters: folder, link, feature, Azure DevOps item, test keys; folder and feature facets."""
import pytest

from qav_shared.keys import test_key as make_test_key

P = "/api/v1/projects/1"


def feature(name, *scenarios):
    return f"Feature: {name}\n" + "".join(f"  {tags}\n  Scenario: {s}\n    Given {s}\n" for s, tags in scenarios)


FILES = [
    ("tests/features/hotel/a.feature", feature("Hotel", ("h1", "@ado:123"))),
    ("tests/features/hotels/booking/b.feature", feature("Hotels booking", ("b1", ""), ("b2", "@ado:456"))),
    ("tests/features/flights_amadeus/c.feature", feature("Amadeus", ("f1", ""))),
    ("tests/features/flightsXamadeus/d.feature", feature("Lookalike", ("x1", ""))),
]


@pytest.fixture
def seeded(client, auth, project_role):
    project_role("member")
    body = {"files": [{"path": p, "content": c} for p, c in FILES]}
    assert client.post(f"{P}/cases/import", json=body, headers=auth()).status_code == 200
    client.post(f"{P}/cases", json={"title": "manual"}, headers=auth())
    return client


def titles(response):
    assert response.status_code == 200, response.text
    return sorted(c["title"] for c in response.json()["items"])


def test_folder_includes_subfolders(seeded, auth):
    assert titles(seeded.get(f"{P}/cases?folder=tests/features/hotels", headers=auth())) == ["b1", "b2"]
    assert titles(seeded.get(f"{P}/cases?folder=tests/features", headers=auth())) == ["b1", "b2", "f1", "h1", "x1"]


def test_folder_matches_whole_segments(seeded, auth):
    assert titles(seeded.get(f"{P}/cases?folder=tests/features/hotel", headers=auth())) == ["h1"]


def test_folder_names_are_matched_literally(seeded, auth):
    assert titles(seeded.get(f"{P}/cases?folder=tests/features/flights_amadeus", headers=auth())) == ["f1"]


def test_linked_feature_and_ado(seeded, auth):
    assert titles(seeded.get(f"{P}/cases?linked=false", headers=auth())) == ["manual"]
    assert "manual" not in titles(seeded.get(f"{P}/cases?linked=true", headers=auth()))
    assert titles(seeded.get(f"{P}/cases?feature=Hotels%20booking", headers=auth())) == ["b1", "b2"]
    assert titles(seeded.get(f"{P}/cases?ado=456", headers=auth())) == ["b2"]
    assert seeded.get(f"{P}/cases?ado=abc", headers=auth()).status_code == 422


def key_of(feature_name, path, scenario):
    return make_test_key(feature_name, path, scenario)


def test_search_includes_only_the_given_keys(seeded, auth):
    body = {"test_keys": [key_of("Hotel", "tests/features/hotel/a.feature", "h1")], "keys_mode": "include"}
    assert titles(seeded.post(f"{P}/cases/search", json=body, headers=auth())) == ["h1"]


def test_search_exclude_keeps_unlinked_cases(seeded, auth):
    body = {"test_keys": [key_of("Hotel", "tests/features/hotel/a.feature", "h1")], "keys_mode": "exclude",
            "folder": None}
    got = titles(seeded.post(f"{P}/cases/search", json=body, headers=auth()))
    assert "h1" not in got and "manual" in got and "b1" in got


def test_exclude_with_no_keys_returns_everything(seeded, auth):
    got = titles(seeded.post(f"{P}/cases/search", json={"test_keys": [], "keys_mode": "exclude"}, headers=auth()))
    assert len(got) == 6


def test_include_with_no_keys_returns_nothing(seeded, auth):
    assert titles(seeded.post(f"{P}/cases/search", json={"test_keys": [], "keys_mode": "include"}, headers=auth())) == []


def test_search_combines_with_other_filters_and_pages(seeded, auth):
    r = seeded.post(f"{P}/cases/search", json={"test_keys": [], "keys_mode": "exclude", "folder": "tests/features/hotels",
                                              "limit": 1, "offset": 0}, headers=auth())
    assert r.json()["total"] == 2 and len(r.json()["items"]) == 1


def test_search_rejects_too_many_keys(seeded, auth):
    r = seeded.post(f"{P}/cases/search", json={"test_keys": ["a" * 64] * 20001}, headers=auth())
    assert r.status_code == 422


def test_folder_facet_counts_subfolders_and_skips_archived(seeded, auth):
    seeded.patch(f"{P}/cases/1", json={"status": "archived"}, headers=auth())  # h1 (TC-1)
    rows = {r["path"]: r["count"] for r in seeded.get(f"{P}/case-folders", headers=auth()).json()}
    assert rows["tests"] == 4 and rows["tests/features"] == 4
    assert rows["tests/features/hotels"] == 2 and rows["tests/features/hotels/booking"] == 2
    assert "tests/features/hotel" not in rows


def test_feature_facet(seeded, auth):
    rows = seeded.get(f"{P}/case-features", headers=auth()).json()
    assert rows == sorted(rows, key=lambda r: r["feature"])
    assert {"feature": "Hotels booking", "count": 2} in rows


def test_viewers_can_read_the_facets_and_search(client, auth, project_role):
    project_role("viewer")
    assert client.get(f"{P}/case-folders", headers=auth()).status_code == 200
    assert client.get(f"{P}/case-features", headers=auth()).status_code == 200
    assert client.post(f"{P}/cases/search", json={}, headers=auth()).status_code == 200
```

The `@ado:123` line goes where the scenario's tags belong (right above `Scenario:`). The `feature()`
helper puts an empty line when `tags` is `""`, which is valid Gherkin. `TC-1` is `h1` because the
import creates cases in plan order (sorted by path), and `tests/features/flights_amadeus/c.feature`
sorts before `hotel`. **Check the actual number** with `GET /cases?feature=Hotel` before
hard-coding the PATCH. Use the `number` it returns instead of `1`.

- [ ] **Step 2: Run the tests and check they fail.** Run `SECRET_KEY=test .venv/Scripts/python -m pytest -q tests/integration/test_case_filters.py`. Expected: FAIL (unknown parameters are ignored, so the assertions fail; `/search` and the facets return 404 or 405).

- [ ] **Step 3: Implement**

`case_service.py`: add `from collections import Counter` and `false` from sqlalchemy. Extend `list_cases`:

```python
def list_cases(db: Session, project_id: int, *, search: Optional[str], labels: List[str], status: Optional[str],
               priority: Optional[str], include_archived: bool, limit: int, offset: int,
               origin: Optional[str] = None, folder: Optional[str] = None, linked: Optional[bool] = None,
               feature: Optional[str] = None, ado: Optional[str] = None,
               test_keys: Optional[List[str]] = None, keys_mode: str = "include"):
    ...existing body up to the label loop...
    if folder:
        query = query.filter(Case.source_path.like(f"{_escape_like(folder.rstrip('/'))}/%", escape="\\"))
    if linked is True:
        query = query.filter(Case.automated_test_key.isnot(None))
    elif linked is False:
        query = query.filter(Case.automated_test_key.is_(None))
    if feature is not None:
        query = query.filter(Case.feature_name == feature)
    if ado is not None:
        query = query.filter(exists().where(CaseLabel.case_id == Case.id, CaseLabel.label == f"ado-{ado}"))
    if test_keys is not None:
        keys = list({k.lower() for k in test_keys})
        if keys_mode == "include":
            query = query.filter(Case.automated_test_key.in_(keys)) if keys else query.filter(false())
        elif keys:
            query = query.filter(or_(Case.automated_test_key.is_(None), Case.automated_test_key.notin_(keys)))
    total = query.count()
    ...


def folder_counts(db: Session, project_id: int) -> List[dict]:
    """Every folder holding an active imported case, counting its subfolders too."""
    counts: Counter = Counter()
    rows = db.query(Case.source_path).filter(
        Case.project_id == project_id, Case.status != "archived", Case.source_path.isnot(None)).all()
    for (path,) in rows:
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            counts["/".join(parts[:i])] += 1
    return [{"path": p, "count": c} for p, c in sorted(counts.items())]


def feature_counts(db: Session, project_id: int) -> List[dict]:
    rows = (
        db.query(Case.feature_name, func.count(Case.id))
        .filter(Case.project_id == project_id, Case.status != "archived", Case.feature_name.isnot(None))
        .group_by(Case.feature_name).order_by(Case.feature_name).all()
    )
    return [{"feature": f, "count": c} for f, c in rows]
```

On SQLite, `notin_` with thousands of values works up to its variable limit (32 766 in current
SQLite builds). The 20 000 cap keeps the request below that.

`schemas/case.py`:

```python
Folder = Annotated[str, StringConstraints(max_length=500, pattern=r"^[^\x00]*$")]
AdoId = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,12}$")]


class CaseSearch(BaseModel):
    """POST /cases/search: GET /cases' filters in a body, plus the test keys of a latest-result filter."""
    model_config = ConfigDict(extra="forbid")

    search: Optional[Annotated[str, StringConstraints(max_length=200, pattern=r"^[^\x00]*$")]] = None
    labels: List[Label] = Field(default_factory=list, max_length=20)
    status: Optional[Status] = None
    priority: Optional[Priority] = None
    origin: Optional[Literal["manual", "imported"]] = None
    include_archived: bool = False
    folder: Optional[Folder] = None
    linked: Optional[bool] = None
    feature: Optional[Folder] = None
    ado: Optional[AdoId] = None
    test_keys: Optional[List[TestKey]] = Field(None, max_length=20000)
    keys_mode: Literal["include", "exclude"] = "include"
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class FolderCount(BaseModel):
    path: str
    count: int


class FeatureCount(BaseModel):
    feature: str
    count: int
```

`endpoints/cases.py`:
- `list_cases` gains these parameters and passes them through:
  - `folder: Optional[str] = Query(None, max_length=500, pattern=NO_NUL)`
  - `linked: Optional[bool] = Query(None)`
  - `feature: Optional[str] = Query(None, max_length=500, pattern=NO_NUL)`
  - `ado: Optional[str] = Query(None, pattern=r"^[0-9]{1,12}$")`
- Add the search route:

```python
@router.post("/search", response_model=CaseList)
def search_cases(
    body: CaseSearch,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    """GET /cases' filters in a body, so a latest-result filter can send thousands of test keys."""
    data = body.model_dump()
    labels, limit, offset = data.pop("labels"), data.pop("limit"), data.pop("offset")
    total, rows = case_service.list_cases(db, access.project_id, labels=labels, limit=limit, offset=offset, **data)
    return {"total": total, "items": [case_service.out(r) for r in rows]}


folders_router = APIRouter()   # mounted at /projects/{project_id}/case-folders
features_router = APIRouter()  # mounted at /projects/{project_id}/case-features


@folders_router.get("", response_model=list[FolderCount])
def list_folders(db: Session = Depends(get_db), access: ProjectAccess = Depends(require_project_role(*READ_ROLES))):
    return case_service.folder_counts(db, access.project_id)


@features_router.get("", response_model=list[FeatureCount])
def list_features(db: Session = Depends(get_db), access: ProjectAccess = Depends(require_project_role(*READ_ROLES))):
    return case_service.feature_counts(db, access.project_id)
```

`search_cases` must be declared before `@router.get("/{number}")` and `@router.patch("/{number}")`.
The path doesn't collide with `GET /{number}` anyway, since this route is a POST.

`api.py`: after the `labels_router` line, add:

```python
api_router.include_router(cases.folders_router, prefix="/projects/{project_id}/case-folders", tags=["cases"])
api_router.include_router(cases.features_router, prefix="/projects/{project_id}/case-features", tags=["cases"])
```

- [ ] **Step 4: Run the new file, then the whole suite, and check they pass.**

- [ ] **Step 5: Commit** — `feat(test-management): filter cases by folder, link, feature and ADO item; search by test keys; folder and feature facets`.

---

### Task 3: ingestion `latest-keys`

**Files:**
- Modify: `platforms/ingestion-service/src/ingestion/service/analytics_service.py` (new `latest_keys`)
- Modify: `platforms/ingestion-service/src/ingestion/api/v1/endpoints/analytics.py` (new route)
- Test: `platforms/ingestion-service/tests/integration/test_latest_keys.py` (new)

**Interfaces:**
- Produces: `GET /api/v1/projects/{id}/analytics/latest-keys?status=&branch=` → `{"keys": [str]}`.

- [ ] **Step 1: Read** `tests/conftest.py` (the `make_key`, `client`, `auth` and `project_role` fixtures) and one existing collect test, to see the `RunUpload` body shape (`run: {ci_provider, branch, started_at, finished_at}`, `results: [{name, status, suite?, class_name?}]`) and its time constraints.

- [ ] **Step 2: Write the failing tests:**

```python
"""GET /analytics/latest-keys: tests whose most recent result has a status (case filters)."""
from datetime import datetime, timedelta, timezone

import pytest

from qav_shared.keys import test_key

URL = "/api/v1/projects/7/analytics/latest-keys"


def upload(client, key, *, branch, started, results):
    run = {"ci_provider": "local", "branch": branch, "started_at": started.isoformat(),
           "finished_at": (started + timedelta(minutes=1)).isoformat()}
    r = client.post("/api/v1/collect/runs", json={"run": run, "results": results},
                    headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 201, r.text


@pytest.fixture
def history(client, make_key, project_role):
    project_role("viewer", project_id=7)
    _, key = make_key(project_id=7)
    now = datetime.now(timezone.utc)
    upload(client, key, branch="main", started=now - timedelta(hours=3), results=[
        {"name": "A", "status": "failed"}, {"name": "B", "status": "failed"}, {"name": "D", "status": "passed"}])
    upload(client, key, branch="main", started=now - timedelta(hours=2), results=[
        {"name": "A", "status": "passed"}, {"name": "C", "status": "skipped"}, {"name": "E", "status": "errored"}])
    upload(client, key, branch="dev", started=now - timedelta(hours=1), results=[{"name": "D", "status": "failed"}])
    return client


def keys(client, auth, query):
    r = client.get(f"{URL}?{query}", headers=auth())
    assert r.status_code == 200, r.text
    return sorted(r.json()["keys"])


def k(*names):
    return sorted(test_key("", "", n) for n in names)


def test_only_the_latest_result_counts(history, auth):
    assert keys(history, auth, "status=passed") == k("A")
    assert keys(history, auth, "status=failed") == k("B", "D", "E")   # errored counts as failed


def test_skipped_and_any(history, auth):
    assert keys(history, auth, "status=skipped") == k("C")
    assert keys(history, auth, "status=any") == k("A", "B", "C", "D", "E")


def test_branch_limits_the_runs(history, auth):
    assert keys(history, auth, "status=passed&branch=main") == k("A", "D")
    assert keys(history, auth, "status=failed&branch=dev") == k("D")


def test_a_bad_status_is_422(history, auth):
    assert history.get(f"{URL}?status=broken", headers=auth()).status_code == 422
```

If the collect endpoint stores `suite` and `class_name` as `""` when they are missing, the keys
are `test_key("", "", name)`. Check `ingest_service` and adjust `k()` only if the stored values
differ.

- [ ] **Step 3: Run the tests and check they fail** (404).

- [ ] **Step 4: Implement**

In `analytics_service.py` (`select`, `func`, `Run` and `RunResult` are already imported there; add
`distinct` if needed):

```python
def latest_keys(db: Session, project_id: int, status: str, branch: Optional[str] = None) -> List[str]:
    """Test keys whose most recent result (by run start) has `status`; failed includes errored.
    `any`: every test with at least one result. Used by the dashboard's latest-result case filter."""
    filters = [Run.project_id == project_id]
    if branch:
        filters.append(Run.branch == branch)
    if status == "any":
        rows = db.execute(select(distinct(RunResult.test_key)).join(Run, Run.id == RunResult.run_id).where(*filters))
        return sorted(k for (k,) in rows)
    ranked = (
        select(RunResult.test_key, RunResult.status,
               func.row_number().over(partition_by=RunResult.test_key,
                                      order_by=(Run.started_at.desc(), Run.id.desc())).label("position"))
        .join(Run, Run.id == RunResult.run_id).where(*filters)
    ).subquery()
    wanted = ("failed", "errored") if status == "failed" else (status,)
    rows = db.execute(select(ranked.c.test_key).where(ranked.c.position == 1, ranked.c.status.in_(wanted)))
    return sorted(k for (k,) in rows)
```

In `endpoints/analytics.py`:

```python
@router.get("/latest-keys")
def latest_keys(
    status: Literal["passed", "failed", "skipped", "any"] = Query(...),
    branch: Optional[str] = Query(None, max_length=255, pattern=NO_NUL),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    """Keys of the tests whose latest result has `status`; the dashboard passes them to test-management."""
    return {"keys": analytics_service.latest_keys(db, access.project_id, status, branch)}
```

- [ ] **Step 5: Run the new file, then the whole ingestion suite, and check they pass.**

- [ ] **Step 6: Commit** — `feat(ingestion): latest-keys lists the tests whose latest result has a status`.

---

### Task 4: `FilterSelect` (dashboard)

**Files:**
- Create: `dashboard/src/components/FilterSelect.tsx`, `dashboard/src/components/FilterSelect.test.tsx`
- Modify: `dashboard/src/index.css` (combobox styles)

**Interfaces:**
- Produces:

```ts
export interface FilterOption { value: string; label: string }
export default function FilterSelect(props: {
  label: string;               // visible label, also the accessible name
  value: string;               // "" = no filter
  options: FilterOption[];     // excluding the empty option
  onChange: (value: string) => void;
  emptyLabel?: string;         // text for "" (default "Any")
  name?: string;
}): JSX.Element
export const SEARCHABLE_OVER = 15;
```

- [ ] **Step 1: Invoke the `ui-ux-pro-max` skill.** Search: `"combobox listbox keyboard" --domain ux`. Follow DESIGN.md "Inputs / Fields": paper fill, strong hairline border, 6px radius, 34px height (44px on coarse pointers), label stacked above at 13px/500, Signal Blue focus with a 2px outline. Use only existing CSS custom properties, so the component works in light and dark mode.

- [ ] **Step 2: Write the failing tests** in `FilterSelect.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import FilterSelect, { FilterOption } from "./FilterSelect";

const opts = (n: number): FilterOption[] =>
  Array.from({ length: n }, (_, i) => ({ value: `v${i}`, label: i === 3 ? "Ação três" : `Option ${i}` }));

function Harness({ n, onSubmit = () => {} }: { n: number; onSubmit?: () => void }) {
  const [value, setValue] = useState("");
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <FilterSelect label="Feature" value={value} options={opts(n)} onChange={setValue} />
      <output data-testid="value">{value}</output>
    </form>
  );
}

test("15 options render a native select", () => {
  render(<Harness n={15} />);
  expect(screen.getByRole("combobox", { name: "Feature" }).tagName).toBe("SELECT");
});

test("16 options render a searchable list with a count", async () => {
  const user = userEvent.setup();
  render(<Harness n={16} />);
  await user.click(screen.getByRole("button", { name: /feature/i }));
  const search = screen.getByRole("combobox", { name: /search feature/i });
  expect(search).toHaveFocus();
  expect(screen.getByText("16 of 16")).toBeInTheDocument();
  await user.type(search, "acao");
  expect(screen.getAllByRole("option")).toHaveLength(1);
  expect(screen.getByText("1 of 16")).toBeInTheDocument();
  await user.clear(search);
  await user.type(search, "zzz");
  expect(screen.getByText("No matches")).toBeInTheDocument();
});

test("keyboard picks an option and Escape returns focus to the trigger", async () => {
  const user = userEvent.setup();
  render(<Harness n={20} />);
  const trigger = screen.getByRole("button", { name: /feature/i });
  await user.click(trigger);
  await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
  expect(screen.getByTestId("value")).toHaveTextContent("v1");
  await user.click(trigger);
  await user.keyboard("{End}{Enter}");
  expect(screen.getByTestId("value")).toHaveTextContent("v19");
  await user.click(trigger);
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

test("enter in the search field picks and does not submit the form", async () => {
  const user = userEvent.setup();
  const submitted = vi.fn();
  render(<Harness n={20} onSubmit={submitted} />);
  await user.click(screen.getByRole("button", { name: /feature/i }));
  await user.keyboard("{ArrowDown}{Enter}");
  expect(submitted).not.toHaveBeenCalled();
  expect(screen.getByTestId("value")).toHaveTextContent("v0");
});

test("the selected value can be cleared", async () => {
  const user = userEvent.setup();
  render(<Harness n={20} />);
  await user.click(screen.getByRole("button", { name: /feature/i }));
  await user.click(screen.getByRole("option", { name: "Option 5" }));
  expect(screen.getByRole("button", { name: /feature/i })).toHaveTextContent("Option 5");
  await user.click(screen.getByRole("button", { name: /clear feature/i }));
  expect(screen.getByTestId("value")).toHaveTextContent("");
});
```

The first ArrowDown makes option 0 active (nothing is active when the list opens). If the
implementation highlights the current value on open instead, keep the tests' intent and adjust the
key presses.

- [ ] **Step 3: Run the tests and check they fail** — `npx vitest run src/components/FilterSelect.test.tsx`.

- [ ] **Step 4: Implement** `FilterSelect.tsx`:
- With `options.length <= SEARCHABLE_OVER`: `<label>{label}<select name value onChange><option value="">{emptyLabel ?? "Any"}</option>{options…}</select></label>`, the same markup the pages use today.
- Otherwise, the combobox:
  - A `<div className="combo-field">` holds a label span `<span id={labelId} className="combo-label">{label}</span>`, styled like `.filters label`.
  - The trigger is `<button type="button" aria-haspopup="listbox" aria-expanded={open} aria-labelledby={`${labelId} ${triggerId}`} id={triggerId}>`. It shows the selected option's label, or `emptyLabel ?? "Any"`.
  - When a value is set, a sibling `<button type="button" aria-label={`Clear ${label}`}>×</button>` calls `onChange("")`.
  - While open, a popup `<div className="combo-popup">` holds:
    - `<input role="combobox" aria-label={`Search ${label}`} aria-expanded="true" aria-controls={listId} aria-activedescendant={activeId} autoFocus>`;
    - `<div className="combo-count" aria-live="polite">{shown} of {total}</div>`;
    - `<ul role="listbox" id={listId} aria-label={label}>`, with each `<li role="option" id aria-selected={value === o.value} onMouseDown={(e) => e.preventDefault()} onClick={() => pick(o.value)}>`;
    - "No matches" when nothing matches.
  - **Matching:** `const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();`, with `norm(o.label).includes(norm(query))`.
  - **Keys on the search input:**
    - ArrowDown/ArrowUp move the active index within the filtered list (starting at none, so the first ArrowDown makes 0 active);
    - Home and End jump to the ends;
    - Enter calls `e.preventDefault()` and picks the active option if there is one;
    - Escape calls `e.preventDefault()`, closes, and focuses the trigger.
  - `pick` calls `onChange(v)`, closes, focuses the trigger and resets the query.
  - A `mousedown` listener on `document` closes the popup when the click is outside the field. Remove it on unmount.
  - The active option scrolls into view: `document.getElementById(activeId)?.scrollIntoView?.({ block: "nearest" })`.

In `index.css`, add `.combo-field` (relative, stacked like `.filters label`), `.combo-trigger` (same
look as the inputs), `.combo-popup` (absolute, `z-index` from the existing scale, `background:
var(--surface-1)`, `border: 1px solid var(--border-strong)`, `max-height: 320px`, `overflow: auto`,
`min-width: 100%`, and on narrow screens `width: min(360px, calc(100vw - 32px))`), and
`[role=option][aria-selected=true]` / `.is-active` states. Use tokens only; no raw hex.

- [ ] **Step 5: Run the tests, then all four CI steps** (`npm run lint`, `npm run typecheck`, `npx vitest run`, `npm run build`), and check they pass.

- [ ] **Step 6: Commit** — `feat(dashboard): FilterSelect — a native select up to 15 options, a searchable list above`.

---

### Task 5: `FolderTree` (dashboard)

**Files:**
- Create: `dashboard/src/components/FolderTree.tsx`, `dashboard/src/components/FolderTree.test.tsx`
- Modify: `dashboard/src/index.css`

**Interfaces:**
- Produces:

```ts
export interface FolderCount { path: string; count: number }
export default function FolderTree(props: {
  folders: FolderCount[];      // from GET /case-folders
  total: number;               // all active cases, for "All cases"
  selected: string;            // "" = all
  onSelect: (path: string) => void;
}): JSX.Element
export function buildTree(folders: FolderCount[]): FolderNode[]  // exported for tests
export interface FolderNode { path: string; name: string; count: number; children: FolderNode[] }
```

- [ ] **Step 1: Invoke `ui-ux-pro-max`.** Search: `"tree view keyboard aria" --domain ux`.

- [ ] **Step 2: Write the failing tests** in `FolderTree.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FolderTree, { buildTree } from "./FolderTree";

const folders = [
  { path: "tests", count: 6 }, { path: "tests/features", count: 6 },
  { path: "tests/features/hotels", count: 4 }, { path: "tests/features/hotels/booking", count: 3 },
  { path: "tests/features/flights", count: 2 },
];

test("leading single-child folders collapse", () => {
  const tree = buildTree(folders);
  expect(tree).toHaveLength(1);
  expect(tree[0]).toMatchObject({ path: "tests/features", name: "features", count: 6 });
  expect(tree[0].children.map((c) => c.name)).toEqual(["flights", "hotels"]);
});

test("nodes show counts and clicking selects, clicking again clears", async () => {
  const user = userEvent.setup();
  const onSelect = vi.fn();
  const { rerender } = render(<FolderTree folders={folders} total={7} selected="" onSelect={onSelect} />);
  expect(screen.getByRole("treeitem", { name: /all cases 7/i })).toBeInTheDocument();
  await user.click(screen.getByRole("treeitem", { name: /features 6/i }));
  expect(onSelect).toHaveBeenLastCalledWith("tests/features");
  rerender(<FolderTree folders={folders} total={7} selected="tests/features" onSelect={onSelect} />);
  await user.click(screen.getByRole("treeitem", { name: /features 6/i }));
  expect(onSelect).toHaveBeenLastCalledWith("");
});

test("keyboard: arrows move, right expands, left collapses, enter selects", async () => {
  const user = userEvent.setup();
  const onSelect = vi.fn();
  render(<FolderTree folders={folders} total={7} selected="" onSelect={onSelect} />);
  screen.getByRole("treeitem", { name: /all cases/i }).focus();
  await user.keyboard("{ArrowDown}");                 // features
  await user.keyboard("{ArrowRight}");                // expand features
  expect(screen.getByRole("treeitem", { name: /hotels 4/i })).toBeInTheDocument();
  await user.keyboard("{ArrowDown}{ArrowDown}{Enter}"); // flights, hotels → select hotels
  expect(onSelect).toHaveBeenLastCalledWith("tests/features/hotels");
  await user.keyboard("{ArrowLeft}");                 // to parent (features)
  await user.keyboard("{ArrowLeft}");                 // collapse features
  expect(screen.queryByRole("treeitem", { name: /hotels 4/i })).not.toBeInTheDocument();
});

test("the path to the selected folder starts expanded", () => {
  render(<FolderTree folders={folders} total={7} selected="tests/features/hotels/booking" onSelect={() => {}} />);
  expect(screen.getByRole("treeitem", { name: /booking 3/i })).toHaveAttribute("aria-selected", "true");
});
```

- [ ] **Step 3: Run the tests and check they fail.**

- [ ] **Step 4: Implement.**
- `buildTree`:
  - Build nodes from the paths, parent by prefix. The name is the last segment. Sort children by name.
  - Then, while the top level has exactly one node and that node has exactly one child, replace the top level with that child. The node keeps its full `path`; its name is its own last segment.
- Rendering:
  - `<ul role="tree" aria-label="Folders">` contains a root `<li role="treeitem" aria-level={1}>` for "All cases" (path `""`), with the top-level nodes as its group. Nested `<ul role="group">` hold the children.
  - Each item has `aria-expanded` (when it has children), `aria-selected={selected === path}` and `aria-level`.
  - The visible text is `<name> <count>`, with the count in a muted span. Make the accessible name contain both, matching `/features 6/` in the tests.
- **Roving tabindex:** exactly one item has `tabIndex=0`: the selected one, else "All cases". Keyboard handling lives on the `ul`, working over the flattened list of visible items:
  - ↑/↓ move to the previous or next visible item;
  - → expands, or moves to the first child if already expanded;
  - ← collapses, or moves to the parent;
  - Enter or Space selects.
- **Clicking** an item selects it, or clears the selection if it's already selected. Clicking the chevron toggles the item.
- **Expanded state:** start with the root and the ancestors of `selected` expanded.

CSS: `.folder-tree` (no list bullets, an indent per level by `padding-left`, counts muted and
right-aligned with `font-variant-numeric: tabular-nums`, the selected item using the accent
background token, a focus ring like inputs). Use tokens only.

- [ ] **Step 5: Run the tests and the four CI steps, and check they pass.**

- [ ] **Step 6: Commit** — `feat(dashboard): FolderTree — case folders as a keyboard-accessible tree`.

---

### Task 6: Cases page filters, API client, and Runs selects

**Files:**
- Modify: `dashboard/src/api/cases.ts` (`Case.feature_name`, new `CaseQuery` fields, `searchCases`, `listFolders`, `listFeatures`)
- Modify: `dashboard/src/api/analytics.ts` (`getLatestKeys`)
- Modify: `dashboard/src/pages/CasesPage.tsx`, `dashboard/src/pages/RunsPage.tsx`, `dashboard/src/index.css`
- Test: `dashboard/src/pages/TestManagement.test.tsx` (Cases tests), `dashboard/src/pages/RunsPage.test.tsx` (if it exists; otherwise the file that tests Runs filters)

**Interfaces:**
- Consumes: Task 2's endpoints, Task 3's endpoint, and the `FilterSelect` and `FolderTree` components.
- Produces:

```ts
// cases.ts
export interface CaseQuery { search?; label?; status?; priority?; origin?; folder?: string; linked?: "true" | "false";
  feature?: string; ado?: string; include_archived?: boolean; limit: number; offset: number }
export interface CaseSearchBody extends Omit<CaseQuery, "label" | "linked"> {
  labels?: string[]; linked?: boolean; test_keys: string[]; keys_mode: "include" | "exclude" }
export function searchCases(projectId: number, body: CaseSearchBody): Promise<{ total: number; items: Case[] }>
export function listFolders(projectId: number): Promise<{ path: string; count: number }[]>
export function listFeatures(projectId: number): Promise<{ feature: string; count: number }[]>
// analytics.ts
export function getLatestKeys(projectId: number, status: "passed" | "failed" | "skipped" | "any"): Promise<{ keys: string[] }>
```

- [ ] **Step 1: Invoke `ui-ux-pro-max`** (layout: side panel and drawer, filter bar density).

- [ ] **Step 2: Write the failing tests.** In `TestManagement.test.tsx`, reuse `asRole`, `renderAt`, `P` and `kase`, and add msw handlers for `${P}/case-folders`, `${P}/case-features` and `${P}/analytics/latest-keys`:

```tsx
const FOLDERS = [{ path: "tests", count: 3 }, { path: "tests/features", count: 3 },
  { path: "tests/features/hotels", count: 2 }, { path: "tests/features/flights", count: 1 }];

function facets() {
  server.use(
    http.get(`${P}/case-labels`, () => HttpResponse.json([{ label: "smoke", count: 1 }, { label: "ado-81284", count: 1 }])),
    http.get(`${P}/case-folders`, () => HttpResponse.json(FOLDERS)),
    http.get(`${P}/case-features`, () => HttpResponse.json([{ feature: "Hotels", count: 2 }])),
  );
}

test("choosing a folder in the tree filters the list and goes into the URL", async () => {
  asRole("member"); facets();
  const seen: URLSearchParams[] = [];
  server.use(http.get(`${P}/cases`, ({ request }) => { seen.push(new URL(request.url).searchParams); return HttpResponse.json({ total: 0, items: [] }); }));
  renderAt("/projects/42/cases");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("treeitem", { name: /features 3/i }));
  await vi.waitFor(() => expect(seen.at(-1)?.get("folder")).toBe("tests/features"));
  expect(screen.getByTestId("where")).toHaveTextContent("folder=tests%2Ffeatures");
});

test("link, feature and ADO filters reach the API", async () => {
  asRole("member"); facets();
  const seen: URLSearchParams[] = [];
  server.use(http.get(`${P}/cases`, ({ request }) => { seen.push(new URL(request.url).searchParams); return HttpResponse.json({ total: 0, items: [] }); }));
  renderAt("/projects/42/cases?linked=false&feature=Hotels&ado=81284");
  await vi.waitFor(() => expect(seen.at(-1)?.get("feature")).toBe("Hotels"));
  expect(seen.at(-1)?.get("linked")).toBe("false");
  expect(seen.at(-1)?.get("ado")).toBe("81284");
});

test("a latest-result filter asks ingestion for keys, then searches with them", async () => {
  asRole("member"); facets();
  let body: Record<string, unknown> | null = null;
  server.use(
    http.get(`${P}/analytics/latest-keys`, ({ request }) => HttpResponse.json({ keys: [new URL(request.url).searchParams.get("status") === "failed" ? "f".repeat(64) : "a".repeat(64)] })),
    http.post(`${P}/cases/search`, async ({ request }) => { body = (await request.json()) as Record<string, unknown>; return HttpResponse.json({ total: 1, items: [kase(1)] }); }),
  );
  renderAt("/projects/42/cases?result=failed&folder=tests%2Ffeatures");
  await vi.waitFor(() => expect(body).not.toBeNull());
  expect(body).toMatchObject({ test_keys: ["f".repeat(64)], keys_mode: "include", folder: "tests/features" });
});

test("never ran asks for any result and excludes those keys", async () => {
  asRole("member"); facets();
  let status = ""; let body: Record<string, unknown> | null = null;
  server.use(
    http.get(`${P}/analytics/latest-keys`, ({ request }) => { status = new URL(request.url).searchParams.get("status") ?? ""; return HttpResponse.json({ keys: [] }); }),
    http.post(`${P}/cases/search`, async ({ request }) => { body = (await request.json()) as Record<string, unknown>; return HttpResponse.json({ total: 0, items: [] }); }),
  );
  renderAt("/projects/42/cases?result=never");
  await vi.waitFor(() => expect(body).not.toBeNull());
  expect(status).toBe("any");
  expect(body).toMatchObject({ test_keys: [], keys_mode: "exclude" });
});

test("when ingestion is down the result filter is skipped with a banner", async () => {
  asRole("member"); facets();
  const seen: URLSearchParams[] = [];
  server.use(
    http.get(`${P}/analytics/latest-keys`, () => HttpResponse.json({ detail: "down" }, { status: 503 })),
    http.get(`${P}/cases`, ({ request }) => { seen.push(new URL(request.url).searchParams); return HttpResponse.json({ total: 1, items: [kase(1)] }); }),
  );
  renderAt("/projects/42/cases?result=passed&label=smoke");
  expect(await screen.findByText(/latest result filter unavailable right now/i)).toBeInTheDocument();
  expect(seen.at(-1)?.get("label")).toBe("smoke");
});

test("clear filters resets everything", async () => {
  asRole("member"); facets();
  server.use(http.get(`${P}/cases`, () => HttpResponse.json({ total: 0, items: [] })));
  renderAt("/projects/42/cases?status=ready&folder=tests&linked=true");
  await userEvent.setup().click(await screen.findByRole("button", { name: /clear filters/i }));
  expect(screen.getByTestId("where")).toHaveTextContent(/^\/projects\/42\/cases$/);
});

test("on narrow screens the folder button opens the tree in a drawer", async () => {
  asRole("member"); facets();
  server.use(http.get(`${P}/cases`, () => HttpResponse.json({ total: 0, items: [] })));
  renderAt("/projects/42/cases");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /folder: all cases/i }));
  const drawer = screen.getByRole("dialog", { name: /folders/i });
  await user.keyboard("{Escape}");
  expect(drawer).not.toBeInTheDocument();
});
```

The panel and the drawer button both exist in the DOM, and CSS shows one of them by width.
Tests that click a treeitem must click the one in the side panel, the first match: use
`findAllByRole(...)[0]` if both trees are mounted. Prefer mounting the drawer's tree only while
the drawer is open, which avoids that.

Existing Cases tests may set a `<select>`'s value for label, status, priority or origin. They
still work, because those lists have 15 options or fewer and so stay native selects. A test that
renders more than 15 labels must use the combobox.

For Runs: if a test file covers its filters, keep it green. The two selects (status, CI) become
`FilterSelect` with the same options, so they stay native.

- [ ] **Step 3: Run the tests and check they fail.**

- [ ] **Step 4: Implement.**
- **API client:**
  - `cases.ts`: `listCases` forwards the new query fields. `searchCases` POSTs the body. Add `listFolders` and `listFeatures`, and `feature_name: string | null` on `Case`.
  - `analytics.ts`: add `getLatestKeys`.
- **CasesPage:**
  - `KEYS` becomes `["q", "label", "status", "priority", "origin", "folder", "linked", "result", "feature", "ado"]`.
  - New queries:
    - `["case-folders", id]` → `listFolders`;
    - `["case-features", id]` → `listFeatures`;
    - `total` for "All cases" is `["cases-total", id]` → `listCases(id, { limit: 1, offset: 0 })`'s `total`.
  - The main query keeps the key `["cases", id, search, offset]`. Its `queryFn`:

```ts
async () => {
  const base = { search: applied.q || undefined, status: (applied.status || undefined) as CaseStatus | undefined,
    priority: (applied.priority || undefined) as Priority | undefined, origin: (applied.origin || undefined) as "manual" | "imported" | undefined,
    folder: applied.folder || undefined, feature: applied.feature || undefined, ado: applied.ado || undefined, limit: PAGE, offset };
  const linked = applied.linked === "true" || applied.linked === "false" ? applied.linked : undefined;
  if (!applied.result) return { page: await listCases(id, { ...base, label: applied.label || undefined, linked }), resultUnavailable: false };
  let keys: string[];
  try {
    keys = (await getLatestKeys(id, applied.result === "never" ? "any" : (applied.result as "passed" | "failed" | "skipped"))).keys;
  } catch {
    return { page: await listCases(id, { ...base, label: applied.label || undefined, linked }), resultUnavailable: true };
  }
  return {
    page: await searchCases(id, { ...base, labels: applied.label ? [applied.label] : [], linked: linked ? linked === "true" : undefined,
      test_keys: keys, keys_mode: applied.result === "never" ? "exclude" : "include" }),
    resultUnavailable: false,
  };
}
```

  - When `resultUnavailable` is true, render
    `<p className="error-banner" role="status">Latest result filter unavailable right now; showing the other filters.</p>`.
  - **Filter form:** every dropdown is a `FilterSelect`:

    | Filter | Options |
    |---|---|
    | Label | from labels, excluding `ado-*` (`label (count)`) |
    | Status | "Draft and ready" as the empty option, then Draft / Ready / Archived |
    | Priority | |
    | Origin | |
    | Link | Linked / Not linked → `true` / `false` |
    | Latest result | Passed / Failed / Skipped / Never ran → `passed` / `failed` / `skipped` / `never` |
    | Feature | `feature (count)` |
    | Azure DevOps | from the `ado-<n>` labels: value `<n>`, label `#<n> (count)` |

    Search stays a text input, and `Apply` submits as today.
  - Next to Apply, a `button type="button"` "Clear filters" calls `setParams(new URLSearchParams())`.
  - **Folder:** choosing one in the tree (or clearing it) updates the URL immediately, keeping the other params: `const next = new URLSearchParams(params); v ? next.set("folder", v) : next.delete("folder"); setParams(next);`. The existing effect on `search` resets the offset.
- **Layout:**

```tsx
<div className={`cases-layout${hidden ? " folders-hidden" : ""}`}>
  <aside className="folder-panel hide-narrow" aria-label="Folders">…header with hide/show button…<FolderTree …/></aside>
  <div className="cases-main">
    <button type="button" className="only-narrow" onClick={() => setDrawer(true)}>Folder: {name || "All cases"} ▾</button>
    …filters, banner, table, paging…
  </div>
</div>
{drawer && <div role="dialog" aria-modal="true" aria-label="Folders" className="drawer" onKeyDown={(e) => e.key === "Escape" && setDrawer(false)}>
  <FolderTree … onSelect={(p) => { choose(p); setDrawer(false); }} /></div>}
```

  - The `hidden` state reads and writes `localStorage["qav.cases.foldersHidden"]`, wrapped in try/catch.
  - `name` is the selected folder's last segment.
  - The drawer focuses its first treeitem when it opens and returns focus to the button when it closes.
- **CSS:**
  - `.cases-layout` is a grid, `grid-template-columns: 260px 1fr`, with `1fr` when `.folders-hidden`.
  - `.folder-panel` is sticky, with `max-height` and `overflow: auto`.
  - `.only-narrow` is `display: none` above 900px.
  - `.hide-narrow` must already hide below 900px; check its breakpoint and align it.
  - `.drawer` is a fixed full-height panel from the left (`width: min(320px, 85vw)`), using surface tokens and a scrim.
- **RunsPage:** replace its two `<select>`s (status, `ci_provider`) with `FilterSelect`. Same options, no behaviour change.

- [ ] **Step 5: Run the four CI steps and check they pass.**

- [ ] **Step 6: Commit** — `feat(dashboard): Cases filter by folder tree, link, latest result, feature and ADO item; Runs selects use FilterSelect`.

---

### Task 7: Gateway route, smoke, docs

**Files:**
- Modify: `gateway/nginx.conf.template:154`, `scripts/smoke_gateway.sh`
- Modify: `platforms/test-management-service/README.md`, `platforms/ingestion-service/README.md`, `TODO.md`, `DESIGN.md` (Inputs / Fields), the spec

- [ ] **Step 1: Write the failing smoke checks.** After the Gherkin import checks (around line 115):

```bash
check "case folders -> test-management-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/case-folders" "${AUTH[@]}"
body_has "... the imported folder is listed" '"path":"tests/features"'
check "case features -> test-management-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/case-features" "${AUTH[@]}"
check "search cases by test keys -> test-management-service" 200 POST "$BASE/api/v1/projects/$PROJECT_ID/cases/search" \
  "${AUTH[@]}" -H "Content-Type: application/json" -d '{"test_keys":[],"keys_mode":"exclude"}'
check "latest-keys -> ingestion-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/analytics/latest-keys?status=any" "${AUTH[@]}"
```

- [ ] **Step 2: Rebuild and run the smoke, and check it fails.** Run `set -a; . ./.env; set +a; docker compose up -d --build test-management-service ingestion-service gateway`, then `bash scripts/smoke_gateway.sh`. The `case-folders` check fails (project-service answers). Never run `docker compose down -v`.

- [ ] **Step 3: Implement.** In `gateway/nginx.conf.template:154`, change the alternation to `(cases|case-labels|case-folders|case-features|suites)`. Then rebuild the gateway.

- [ ] **Step 4: Run the smoke again and check every check passes.**

- [ ] **Step 5: Update the docs.**
- **test-management README:** the new `GET /cases` filters, `POST /cases/search`, `/case-folders` and `/case-features`.
- **ingestion README:** `latest-keys`.
- **DESIGN.md**, under "Inputs / Fields": add the rule "A filter dropdown with more than 15 options is a searchable list (FilterSelect): a search field at the top of the open list, matching anywhere and ignoring accents, with an 'x of y' count."
- **TODO.md:** an entry marked `[x]`, "(2026-10-06)".
- **Spec:**
  - Under "Used for", note that Runs' branch, environment and author are free-text inputs, so only its status and CI selects use `FilterSelect`.
  - Note that the case editor's test picker is a search input and is unchanged.

- [ ] **Step 6: Commit** — `feat(gateway): route case folders and features; smoke and docs for case filters`.
