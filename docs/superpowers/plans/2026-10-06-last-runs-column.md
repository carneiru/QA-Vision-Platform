# Last Runs Column Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Cases list gets a "Last runs" column with a 10-bar strip per case, one bar per project run. Green is passed, red failed, yellow re-run, and an outline means the test did not run.

**Architecture:**
- **Ingestion** gains `POST /analytics/run-strip`. It takes the page's test keys, finds the project's last N runs, and returns one status per key per run. That takes one query for the runs and one grouped query for the results.
- **The dashboard** calls it with the linked keys of the current page and renders `RunStrip` in a new column, with a legend.

**Tech Stack:** FastAPI, SQLAlchemy, pytest; React + TS, TanStack Query, vitest + msw.

**Spec:** `docs/superpowers/specs/2026-10-06-last-runs-column-design.md`

## Global Constraints

- **Endpoint:** `POST /api/v1/projects/{id}/analytics/run-strip`. The body is `{test_keys: 1..200 × 64-hex, limit: 1..20 (default 10), branch?: ≤255, no NUL}`. Anything else is 422. Every project role (READ_ROLES) may call it.
- **Response:** `{"runs": [{"id", "started_at", "branch"}...], "statuses": {key: [status|null, ...]}}`.
  - `runs` are the project's last `limit` runs (`started_at` desc, then `id` desc), returned in oldest→newest order. With `branch`, only runs on that branch count.
  - Every requested key appears in `statuses`, in lowercase, with one entry per run.
- **Status per (key, run):**
  - more than one result row → `"rerun"`;
  - else `passed` → `"passed"`;
  - `failed` or `errored` → `"failed"`;
  - `skipped` → `"skipped"`;
  - no row → `null`.
- **Dashboard rendering:**
  - Bars are 6×18px with a 2px gap.
  - Colours are `--status-passed`, `--status-failed` and a new `--status-rerun` (amber, with light and dark values), each ≥3:1 against the cell background.
  - Shape cues:
    - failed has a notch at the top (`clip-path`);
    - re-run has diagonal stripes (`repeating-linear-gradient`);
    - skipped has a dashed outline;
    - "not in run" has a solid hairline outline and no fill.
  - Each bar is a link to `/projects/{id}/runs/{runId}`, with `aria-label` and `title` reading "Run #433, 6 Oct 14:02: failed".
  - The strip has `role="group"` and an `aria-label` such as "Last 10 runs: 7 passed, 2 failed, 1 re-run", counting only non-zero kinds and including "not run" and "skipped".
  - A case with no `automated_test_key` shows the muted text "not linked".
  - While loading, show 10 grey skeleton bars.
  - If the request fails, show "—" in the cell; the page keeps working.
- **Column placement:** "Last runs" goes after Title, as `hide-narrow`. A legend sits beside the table, in visible text.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Work on master and never push. Commit only your own paths: `git add <files> && git commit -m "<msg>" -- <files>`.
- Never run two pytest processes in the same service at once.
- Dashboard: invoke `ui-ux-pro-max` first. Before reporting, run `npm run lint`, `npm run typecheck`, `npx vitest run` and `npm run build`, with pristine output. Use tokens only and no `any`.

## Review Focus

1. **Results from another project's run with the same key** must never appear. Pinned in Task 1 (`test_other_projects_runs_are_invisible`).
2. **A key in lowercase vs uppercase hex** must give the same result. Pinned in Task 1 (`test_keys_are_case_insensitive`).
3. **A page where no case is linked** must not call run-strip, because the endpoint requires at least 1 key. Pinned in Task 3 (`no linked cases means no run-strip request`).
4. **A run with a retry where the last attempt passed** must show as re-run, not passed. Pinned in Task 1 (`test_a_retried_test_is_a_rerun_whatever_the_outcome`).
5. **Dark mode contrast** of the amber bar against the dark cell. This is checked by computing the ratio in Task 2 and recording it in the report.

---

### Task 1: ingestion `run-strip`

**Files:**
- Modify: `platforms/ingestion-service/src/ingestion/service/analytics_service.py` (new `run_strip`)
- Modify: `platforms/ingestion-service/src/ingestion/api/v1/endpoints/analytics.py` (new route and body schema)
- Test: `platforms/ingestion-service/tests/integration/test_run_strip.py` (new)

**Interfaces:**
- Produces: `POST /analytics/run-strip`, as described in Global Constraints.

- [ ] **Step 1: Write the failing tests.** Reuse the upload helper pattern from `tests/integration/test_latest_keys.py`: `make_key`, `client`, `project_role`, and `POST /api/v1/collect/runs` with `run` and `results`.

```python
"""POST /analytics/run-strip: each test's status in the project's last N runs (Cases 'Last runs')."""
from datetime import datetime, timedelta, timezone

import pytest

from qav_shared.keys import test_key

URL = "/api/v1/projects/7/analytics/run-strip"
A, B, C = (test_key("", "", n) for n in "ABC")


def upload(client, key, *, started, results, branch="main"):
    run = {"ci_provider": "local", "branch": branch, "started_at": started.isoformat(),
           "finished_at": (started + timedelta(minutes=1)).isoformat()}
    r = client.post("/api/v1/collect/runs", json={"run": run, "results": results},
                    headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 201, r.text


@pytest.fixture
def runs(client, make_key, project_role):
    project_role("viewer", project_id=7)
    _, key = make_key(project_id=7)
    now = datetime.now(timezone.utc)
    upload(client, key, started=now - timedelta(hours=4), results=[{"name": "A", "status": "passed"}])
    upload(client, key, started=now - timedelta(hours=3), results=[
        {"name": "A", "status": "failed"}, {"name": "A", "status": "passed"}, {"name": "B", "status": "errored"}])
    upload(client, key, started=now - timedelta(hours=2), branch="dev", results=[{"name": "A", "status": "skipped"}])
    upload(client, key, started=now - timedelta(hours=1), results=[{"name": "B", "status": "passed"}])
    return client


def strip(client, auth, **body):
    r = client.post(URL, json={"test_keys": [A, B, C], **body}, headers=auth())
    assert r.status_code == 200, r.text
    return r.json()


def test_runs_are_oldest_to_newest_and_aligned_for_every_key(runs, auth):
    data = strip(runs, auth)
    assert len(data["runs"]) == 4
    assert [r["started_at"] for r in data["runs"]] == sorted(r["started_at"] for r in data["runs"])
    assert data["statuses"][A] == ["passed", "rerun", "skipped", None]
    assert data["statuses"][B] == [None, "failed", None, "passed"]   # errored counts as failed
    assert data["statuses"][C] == [None, None, None, None]


def test_a_retried_test_is_a_rerun_whatever_the_outcome(runs, auth):
    assert strip(runs, auth)["statuses"][A][1] == "rerun"


def test_limit_keeps_the_newest_runs(runs, auth):
    data = strip(runs, auth, limit=2)
    assert data["statuses"][A] == ["skipped", None]


def test_branch_only_counts_that_branchs_runs(runs, auth):
    data = strip(runs, auth, branch="main")
    assert len(data["runs"]) == 3 and data["statuses"][A] == ["passed", "rerun", None]


def test_keys_are_case_insensitive(runs, auth):
    r = runs.post(URL, json={"test_keys": [A.upper()]}, headers=auth())
    assert r.json()["statuses"][A] == ["passed", "rerun", "skipped", None]


def test_other_projects_runs_are_invisible(runs, auth, make_key, project_role):
    project_role("viewer", project_id=8)
    _, other = make_key(project_id=8)
    upload(runs, other, started=datetime.now(timezone.utc), results=[{"name": "A", "status": "failed"}])
    assert len(strip(runs, auth)["runs"]) == 4


@pytest.mark.parametrize("body", [{"test_keys": []}, {"test_keys": ["x"]}, {"test_keys": [A] * 201},
                                  {"test_keys": [A], "limit": 21}, {"test_keys": [A], "branch": "a\x00"}])
def test_bad_bodies_are_422(runs, auth, body):
    assert runs.post(URL, json=body, headers=auth()).status_code == 422
```

The two results for A in one run (failed, then passed) form a retry. If the collect endpoint
collapses duplicates inside one upload, read how `ingest_service` stores repeated names and adjust
the fixture so two rows exist, for example by giving them different `suite` values with the same
key. Do not change the asserted semantics.

- [ ] **Step 2: Run the tests and check they fail** (404 or 405).

- [ ] **Step 3: Implement.** In `analytics_service.py`:

```python
def run_strip(db: Session, project_id: int, keys: List[str], limit: int = 10,
              branch: Optional[str] = None) -> dict:
    """Each test's status in the project's last `limit` runs, oldest to newest (Cases 'Last runs').
    More than one result row for a test in a run is a re-run; errored counts as failed."""
    filters = [Run.project_id == project_id]
    if branch:
        filters.append(Run.branch == branch)
    recent = db.execute(
        select(Run.id, Run.started_at, Run.branch).where(*filters)
        .order_by(Run.started_at.desc(), Run.id.desc()).limit(limit)
    ).all()
    recent = list(reversed(recent))
    keys = sorted({k.lower() for k in keys})
    statuses = {k: [None] * len(recent) for k in keys}
    if recent and keys:
        position = {run.id: i for i, run in enumerate(recent)}
        rows = db.execute(
            select(RunResult.run_id, RunResult.test_key, func.count(RunResult.id), func.max(RunResult.status))
            .where(RunResult.run_id.in_(list(position)), RunResult.test_key.in_(keys))
            .group_by(RunResult.run_id, RunResult.test_key)
        ).all()
        for run_id, key, count, status in rows:
            if count > 1:
                value = "rerun"
            else:
                value = "failed" if status in ("failed", "errored") else status
            statuses[key][position[run_id]] = value
    return {"runs": [{"id": r.id, "started_at": r.started_at, "branch": r.branch} for r in recent],
            "statuses": statuses}
```

`func.max(status)` is only read when `count == 1`, so taking the max is safe.

In `endpoints/analytics.py`:

```python
class RunStripIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_keys: List[Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{64}$")]] = Field(min_length=1, max_length=200)
    limit: int = Field(10, ge=1, le=20)
    branch: Optional[Annotated[str, StringConstraints(max_length=255, pattern=NO_NUL)]] = None


@router.post("/run-strip")
def run_strip(
    body: RunStripIn,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    """Last-runs strip for the Cases list: the page's keys against the project's last runs."""
    return analytics_service.run_strip(db, access.project_id, body.test_keys, body.limit, body.branch)
```

Place `RunStripIn` with the other schemas if this service keeps them in `schemas/`. Follow the
local convention, and import `BaseModel`, `ConfigDict`, `Field`, `StringConstraints`, `Annotated`
and `List` as needed.

- [ ] **Step 4: Run the new file, then the whole suite, and check they pass.**

- [ ] **Step 5: Commit** — `feat(ingestion): run-strip returns each test's status in the project's last runs`.

---

### Task 2: `RunStrip` component

**Files:**
- Create: `dashboard/src/components/RunStrip.tsx`, `dashboard/src/components/RunStrip.test.tsx`
- Modify: `dashboard/src/index.css` (`--status-rerun` light and dark, `.run-strip` styles)

**Interfaces:**
- Produces:

```ts
export type StripStatus = "passed" | "failed" | "rerun" | "skipped" | null;
export interface StripRun { id: number; started_at: string; branch: string | null }
export default function RunStrip(props: { projectId: number; runs: StripRun[]; statuses: StripStatus[] }): JSX.Element
export function RunStripSkeleton(): JSX.Element
export function stripSummary(statuses: StripStatus[]): string   // "Last 10 runs: 7 passed, 2 failed, 1 re-run"
```

- [ ] **Step 1: Invoke `ui-ux-pro-max`.** Searches: `"color not only status" --domain ux` and `"sparkline status bars accessible" --domain chart`.

- [ ] **Step 2: Write the failing tests:**

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import RunStrip, { stripSummary } from "./RunStrip";

const runs = [433, 434, 435, 436].map((id, i) => ({ id, started_at: `2026-10-06T1${i}:02:00Z`, branch: "main" }));

test("the strip is a labelled group summarising the runs", () => {
  render(<MemoryRouter><RunStrip projectId={5} runs={runs} statuses={["passed", "failed", "rerun", null]} /></MemoryRouter>);
  expect(screen.getByRole("group", { name: "Last 4 runs: 1 passed, 1 failed, 1 re-run, 1 not run" })).toBeInTheDocument();
});

test("each bar links to its run and says what happened", () => {
  render(<MemoryRouter><RunStrip projectId={5} runs={runs} statuses={["passed", "failed", "rerun", "skipped"]} /></MemoryRouter>);
  const failed = screen.getByRole("link", { name: /run #434.*failed/i });
  expect(failed).toHaveAttribute("href", "/projects/5/runs/434");
  expect(failed).toHaveClass("bar-failed");
  expect(screen.getByRole("link", { name: /run #435.*re-run/i })).toHaveClass("bar-rerun");
  expect(screen.getByRole("link", { name: /run #436.*skipped/i })).toHaveClass("bar-skipped");
});

test("a run the test was not in is an outlined bar", () => {
  render(<MemoryRouter><RunStrip projectId={5} runs={runs} statuses={[null, null, null, "passed"]} /></MemoryRouter>);
  expect(screen.getByRole("link", { name: /run #433.*not run/i })).toHaveClass("bar-none");
});

test("summary only names kinds that occur", () => {
  expect(stripSummary(["passed", "passed"])).toBe("Last 2 runs: 2 passed");
});
```

- [ ] **Step 3: Run the tests and check they fail.**

- [ ] **Step 4: Implement.**
- Render `<div className="run-strip" role="group" aria-label={stripSummary(statuses)}>`.
- Each bar is a `<Link className={`run-bar bar-${status ?? "none"}`} to={`/projects/${projectId}/runs/${run.id}`} aria-label={label} title={label}>`.
- The label is `Run #${id}, ${formatted date}: ${word}`, where the word is passed, failed, re-run, skipped or not run.
- Format the date with `Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })`.
- `RunStripSkeleton` renders 10 `.run-bar.bar-loading` spans with `aria-hidden`, plus a visually hidden "Loading last runs".

CSS:
- `.run-strip` is `display: inline-flex` with `gap: 2px`.
- `.run-bar` is 6×18px, `border-radius: 1px`, `display: inline-block`. Its link focus ring uses the global `:focus-visible`.
- Bar styles:
  - `.bar-passed` uses `--status-passed`;
  - `.bar-failed` uses `--status-failed` with `clip-path: polygon(0 3px, 50% 0, 100% 3px, 100% 100%, 0 100%)` for the notch;
  - `.bar-rerun` uses `--status-rerun` with a `repeating-linear-gradient(135deg, …)` stripe of a darker tone;
  - `.bar-skipped` has `background: transparent` and `outline: 1px dashed var(--text-secondary)`;
  - `.bar-none` has `background: transparent` and `box-shadow: inset 0 0 0 1px var(--border-strong)`;
  - `.bar-loading` uses `--surface-2`.
- Add `--status-rerun` to `:root` (an amber such as `#c98a00`) and to the dark block (a lighter amber).
- Compute the contrast against the table cell background in both themes. It must be ≥3:1; record the ratios in the report.

- [ ] **Step 5: Run the tests and the four CI steps, and check they pass.**

- [ ] **Step 6: Commit** — `feat(dashboard): RunStrip — a run-by-run status strip with shape cues and labels`.

---

### Task 3: "Last runs" column on Cases

**Files:**
- Modify: `dashboard/src/api/analytics.ts` (`getRunStrip`)
- Modify: `dashboard/src/pages/CasesPage.tsx` (column, query, legend)
- Modify: `dashboard/src/index.css` (legend)
- Test: `dashboard/src/pages/TestManagement.test.tsx`

**Interfaces:**
- Consumes: Task 1's endpoint and Task 2's component.
- Produces: `getRunStrip(projectId, testKeys: string[], limit = 10): Promise<{ runs: StripRun[]; statuses: Record<string, StripStatus[]> }>`.

- [ ] **Step 1: Invoke `ui-ux-pro-max`** (table column density, legend placement).

- [ ] **Step 2: Write the failing tests** in `TestManagement.test.tsx`. Reuse the existing helpers and `beforeEach` defaults, and add a default handler for `${P}/analytics/run-strip` there that returns empty data.

```tsx
test("linked cases show their last runs; unlinked say not linked", async () => {
  asRole("member");
  const KEY = "b".repeat(64);
  let asked: string[] = [];
  server.use(
    http.get(`${P}/cases`, () => HttpResponse.json({ total: 2, items: [kase(1, { automated_test_key: KEY }), kase(2)] })),
    http.post(`${P}/analytics/run-strip`, async ({ request }) => {
      asked = ((await request.json()) as { test_keys: string[] }).test_keys;
      return HttpResponse.json({ runs: [{ id: 9, started_at: "2026-10-06T10:00:00Z", branch: "main" }], statuses: { [KEY]: ["failed"] } });
    }),
  );
  renderAt("/projects/42/cases");
  expect(await screen.findByRole("group", { name: "Last 1 runs: 1 failed" })).toBeInTheDocument();
  expect(asked).toEqual([KEY]);
  expect(screen.getByText("not linked")).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: /last runs/i })).toBeInTheDocument();
});

test("no linked cases means no run-strip request", async () => {
  asRole("member");
  let called = false;
  server.use(
    http.get(`${P}/cases`, () => HttpResponse.json({ total: 1, items: [kase(1)] })),
    http.post(`${P}/analytics/run-strip`, () => { called = true; return HttpResponse.json({ runs: [], statuses: {} }); }),
  );
  renderAt("/projects/42/cases");
  await screen.findByText("not linked");
  expect(called).toBe(false);
});

test("a failing run-strip leaves the list usable", async () => {
  asRole("member");
  const KEY = "c".repeat(64);
  server.use(
    http.get(`${P}/cases`, () => HttpResponse.json({ total: 1, items: [kase(1, { automated_test_key: KEY })] })),
    http.post(`${P}/analytics/run-strip`, () => HttpResponse.json({ detail: "down" }, { status: 503 })),
  );
  renderAt("/projects/42/cases");
  expect(await screen.findByRole("link", { name: "Case 1" })).toBeInTheDocument();
  expect(await screen.findByLabelText(/last runs unavailable/i)).toBeInTheDocument();
});
```

"Last 1 runs" reads awkwardly. If you make `stripSummary` say "Last run: …" for a single run,
update both tests consistently.

- [ ] **Step 3: Run the tests and check they fail.**

- [ ] **Step 4: Implement.**
- **API client:** in `analytics.ts`, `getRunStrip` POSTs `{ test_keys, limit }`.
- **CasesPage:**
  - After the page query resolves, compute `keys` as the unique `automated_test_key`s of the items, sorted.
  - Add `useQuery({ queryKey: ["run-strip", id, keys], queryFn: () => getRunStrip(id, keys), enabled: keys.length > 0 })`.
  - Add the header `<th className="hide-narrow">Last runs</th>` after Title.
  - The cell shows one of:
    - `RunStrip` with `runs` and `statuses[c.automated_test_key]`;
    - `<span className="muted">not linked</span>`;
    - the skeleton while loading;
    - on error, `<span aria-label="Last runs unavailable">—</span>`.
- **Legend:** a small inline legend beside the table, in visible text with sample bars: "Passed", "Failed", "Re-run", "Skipped", "Didn't run". Hide it with `hide-narrow`, like the column.
- **Invalidation:** the cases page already refetches cases. Make the run-strip key depend on `keys` only; runs change rarely and `staleTime` is 60s.

- [ ] **Step 5: Run the four CI steps and check they pass.**

- [ ] **Step 6: Commit** — `feat(dashboard): Cases 'Last runs' column with a legend`.

---

### Task 4: Smoke and docs

**Files:**
- Modify: `scripts/smoke_gateway.sh`, `platforms/ingestion-service/README.md`, `TODO.md`, `DESIGN.md` (Status Dot and Badges: the strip and its shape cues)

- [ ] **Step 1: Add a smoke check.** After the latest-keys check:

```bash
check "run-strip -> ingestion-service" 200 POST "$BASE/api/v1/projects/$PROJECT_ID/analytics/run-strip" \
  "${AUTH[@]}" -H "Content-Type: application/json" -d "{\"test_keys\":[\"$(printf 'a%.0s' $(seq 64))\"]}"
body_has "... returns statuses" '"statuses"'
```

- [ ] **Step 2: Rebuild and run the smoke, and check it passes.** Run `set -a; . ./.env; set +a; docker compose up -d --build ingestion-service dashboard gateway`, then `bash scripts/smoke_gateway.sh`. Never run `down -v`.

- [ ] **Step 3: Update the docs.**
- **ingestion README:** the `run-strip` row (body, response, status rules, limits).
- **DESIGN.md:** the run-strip rule, covering colours and the shape cues for colour-blind users.
- **TODO.md:** an `[x]` entry dated 2026-10-06 next to the case-filters entry.

- [ ] **Step 4: Commit** — `docs: run-strip endpoint and Last runs column; smoke`.
