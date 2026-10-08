import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { delay, http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import CasesPage from "./CasesPage";
import CaseEditorPage from "./CaseEditorPage";
import SuiteDetailPage from "./SuiteDetailPage";

const P = "/api/v1/projects/42";
const TARGET = { available: true, configured: true, provider: "github", repo: "acme/obt", workflow: "qeos-run.yml",
  ref: "main", token_last4: "a1b2", token_expires_at: null, updated_at: "2026-10-07T10:00:00Z", last_change: null };

const kase = (number: number, extra: object = {}) => ({
  number, key: `TC-${number}`, title: `Case ${number}`, description: null, steps: [], labels: [], priority: "medium",
  status: "draft", automated_test_key: null, automated_name: null, created_by: 1, created_at: "2026-10-06T10:00:00Z",
  updated_by: null, updated_at: null, suites: [], source_path: "tests/features/a.feature", gherkin: "Scenario: x",
  feature_name: "A", ...extra,
});

const runRequest = (extra: object = {}) => ({
  id: 9, requested_by: 7, requested_at: new Date().toISOString(),
  selection: [{ case_number: 1, path: "tests/features/a.feature", name: "Case 1" }], case_count: 1, suite_id: null,
  // After a 200 dispatch the request carries its GitHub run from the start
  status: "queued", conclusion: null, github_run_id: 501, github_run_url: "https://github.com/acme/obt/actions/runs/501",
  stopped_by: null, stopped_at: null,
  error: null, checked_at: null, refreshing: true, skipped_manual: 0, ...extra,
});

function asRole(role: string) {
  server.use(http.get(P, () => HttpResponse.json({ id: 42, organization_id: 1, name: "Web", my_role: role })));
}

beforeEach(() => {
  asRole("member");
  server.use(
    http.get(`${P}/case-features`, () => HttpResponse.json([])),
    http.get(`${P}/case-folders`, () => HttpResponse.json([])),
    http.get(`${P}/case-labels`, () => HttpResponse.json([])),
    http.get(`${P}/cases`, () => HttpResponse.json({ total: 0, items: [] })),
    http.get(`${P}/ci-target`, () => HttpResponse.json(TARGET)),
    http.get(`${P}/run-requests`, () => HttpResponse.json({ total: 0, items: [] })),
  );
});

function renderAt(url: string) {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/projects/:projectId/cases" element={<CasesPage />} />
          <Route path="/projects/:projectId/cases/:caseNumber" element={<CaseEditorPage />} />
          <Route path="/projects/:projectId/suites/:suiteId" element={<SuiteDetailPage />} />
          <Route path="/projects/:projectId/settings" element={<p>Settings page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return qc;
}

function listing(items: object[], total = items.length) {
  server.use(http.get(`${P}/cases`, ({ request }) => {
    const sp = new URL(request.url).searchParams;
    const offset = Number(sp.get("offset") ?? 0);
    const limit = Number(sp.get("limit") ?? 50);
    return HttpResponse.json({ total, items: items.slice(offset, offset + limit) });
  }));
}

test("Run on an imported case asks first, then starts it", async () => {
  let sent: unknown = null;
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.post(`${P}/run-requests`, async ({ request }) => { sent = await request.json(); return HttpResponse.json(runRequest(), { status: 201 }); }),
  );
  renderAt("/projects/42/cases/1");
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  const dialog = screen.getByRole("dialog", { name: "Run 1 test?" });
  expect(within(dialog).getByText("TC-1 · Case 1")).toBeInTheDocument();
  expect(within(dialog).getByText("acme/obt @ main")).toBeInTheDocument();
  expect(within(dialog).getByText("Tests may create real bookings in staging")).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
  expect(sent).toBeNull();
  await userEvent.click(within(dialog).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(sent).toEqual({ case_numbers: [1] }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});

test("Cancel and Escape close the dialog without a request and return focus to Run", async () => {
  let posts = 0;
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.post(`${P}/run-requests`, () => { posts += 1; return HttpResponse.json(runRequest(), { status: 201 }); }),
  );
  renderAt("/projects/42/cases/1");
  const run = await screen.findByRole("button", { name: "Run" });
  await userEvent.click(run);
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(run).toHaveFocus();
  await userEvent.click(run);
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(run).toHaveFocus();
  expect(posts).toBe(0);
});

test("a double click on Run starts one run", async () => {
  let posts = 0;
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.post(`${P}/run-requests`, async () => { posts += 1; await delay(50); return HttpResponse.json(runRequest(), { status: 201 }); }),
  );
  renderAt("/projects/42/cases/1");
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  await userEvent.dblClick(within(screen.getByRole("dialog")).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(posts).toBe(1);
});

test("the server's refusal shows inside the dialog", async () => {
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.post(`${P}/run-requests`, () => HttpResponse.json(
      { detail: "TC-1: re-import the .feature files first" }, { status: 422 })),
  );
  renderAt("/projects/42/cases/1");
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  const dialog = screen.getByRole("dialog");
  await userEvent.click(within(dialog).getByRole("button", { name: "Run" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("re-import the .feature files first");
});

test("a manual case has no Run", async () => {
  server.use(http.get(`${P}/cases/2`, () => HttpResponse.json(kase(2, { source_path: null, gherkin: null }))));
  renderAt("/projects/42/cases/2");
  await screen.findByRole("heading", { name: /TC-2/ });
  expect(screen.queryByRole("button", { name: "Run" })).not.toBeInTheDocument();
});

test("selected rows run together; manual cases have no checkbox", async () => {
  let sent: unknown = null;
  listing([kase(1), kase(2, { source_path: null }), kase(3)]);
  server.use(http.post(`${P}/run-requests`, async ({ request }) => { sent = await request.json(); return HttpResponse.json(runRequest(), { status: 201 }); }));
  renderAt("/projects/42/cases?group=scenario");
  await userEvent.click(await screen.findByRole("checkbox", { name: "Select TC-1 Case 1" }));
  expect(screen.queryByRole("checkbox", { name: /TC-2/ })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("checkbox", { name: "Select TC-3 Case 3" }));
  await userEvent.click(screen.getByRole("button", { name: "Run selected (2)" }));
  const dialog = screen.getByRole("dialog", { name: "Run 2 tests?" });
  await userEvent.click(within(dialog).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(sent).toEqual({ case_numbers: [1, 3] }));
  await waitFor(() => expect(screen.queryByRole("button", { name: /Run selected/ })).not.toBeInTheDocument());
});

test("the dialog lists ten cases and then how many more", async () => {
  listing(Array.from({ length: 12 }, (_, i) => kase(i + 1)));
  renderAt("/projects/42/cases?group=scenario");
  await userEvent.click(await screen.findByRole("checkbox", { name: "Select all imported cases on this page" }));
  await userEvent.click(screen.getByRole("button", { name: "Run selected (12)" }));
  const dialog = screen.getByRole("dialog", { name: "Run 12 tests?" });
  expect(within(dialog).getAllByRole("listitem")).toHaveLength(10);
  expect(within(dialog).getByText("+2 more")).toBeInTheDocument();
});

test("at most 200 cases can be selected", async () => {
  listing(Array.from({ length: 260 }, (_, i) => kase(i + 1)));
  renderAt("/projects/42/cases?group=scenario");
  for (let page = 0; page < 4; page++) {
    await userEvent.click(await screen.findByRole("checkbox", { name: "Select all imported cases on this page" }));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByRole("link", { name: `Case ${(page + 1) * 50 + 1}` });
  }
  expect(screen.getByRole("button", { name: "Run selected (200)" })).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "Select TC-201 Case 201" })).toBeDisabled();
  expect(screen.getByText("At most 200 cases per run")).toBeInTheDocument();
});

test("Run suite sends the suite id", async () => {
  let sent: unknown = null;
  server.use(
    http.get(`${P}/suites/5`, () => HttpResponse.json({
      id: 5, name: "Smoke", description: null, case_count: 2, created_at: "2026-10-06T10:00:00Z", updated_at: null,
      cases: [1, 2].map((n) => ({ number: n, key: `TC-${n}`, title: `Case ${n}`, status: "draft", priority: "medium",
        labels: [], automated_test_key: null })) })),
    http.post(`${P}/run-requests`, async ({ request }) => { sent = await request.json(); return HttpResponse.json(runRequest(), { status: 201 }); }),
  );
  renderAt("/projects/42/suites/5");
  await userEvent.click(await screen.findByRole("button", { name: "Run suite" }));
  await userEvent.click(within(screen.getByRole("dialog", { name: "Run 2 tests?" })).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(sent).toEqual({ suite_id: 5 }));
});

test.each([
  ["no target", "member", { ...TARGET, configured: false }, [], "Configure in Settings"],
  ["a viewer", "viewer", TARGET, [], "Viewers can't run tests"],
  ["a billing manager", "billing_manager", TARGET, [], "Viewers can't run tests"],
  ["an active run", "member", TARGET, [runRequest({ status: "running" })], "A run is in progress"],
  ["an expired token", "member", { ...TARGET, token_expires_at: "2020-01-01T00:00:00Z" }, [], "GitHub token expired"],
])("Run is disabled, with the reason, for %s", async (_, role, target, items, reason) => {
  asRole(role);
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.get(`${P}/ci-target`, () => HttpResponse.json(target)),
    http.get(`${P}/run-requests`, () => HttpResponse.json({ total: items.length, items })),
  );
  renderAt("/projects/42/cases/1");
  expect(await screen.findByText(reason)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Run" })).toBeDisabled();
});

test("Configure in Settings links to the project's settings", async () => {
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.get(`${P}/ci-target`, () => HttpResponse.json({ ...TARGET, configured: false })),
  );
  renderAt("/projects/42/cases/1");
  expect(await screen.findByRole("link", { name: "Configure in Settings" })).toHaveAttribute("href", "/projects/42/settings");
});

test("while the run is starting, Cancel is disabled and Escape does nothing", async () => {
  let posts = 0;
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.post(`${P}/run-requests`, async () => { posts += 1; await held; return HttpResponse.json(runRequest(), { status: 201 }); }),
  );
  renderAt("/projects/42/cases/1");
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  const dialog = screen.getByRole("dialog");
  await userEvent.click(within(dialog).getByRole("button", { name: "Run" }));
  expect(await within(dialog).findByRole("button", { name: "Starting…" })).toBeDisabled();
  expect(within(dialog).getByRole("button", { name: "Cancel" })).toBeDisabled();
  await userEvent.keyboard("{Escape}");
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(posts).toBe(1);
  release();
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(posts).toBe(1);
});

test("a 409 run_active closes the dialog, says why and turns Play off", async () => {
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.post(`${P}/run-requests`, () => {
      // someone else's run is now the newest one
      server.use(http.get(`${P}/run-requests`, () => HttpResponse.json({ total: 1, items: [runRequest({ status: "running" })] })));
      return HttpResponse.json({ detail: { code: "run_active", message: "A run is in progress", run_request_id: 9 } }, { status: 409 });
    }),
  );
  renderAt("/projects/42/cases/1");
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Run" }));
  // the server's message and the gate's reason are the same text: shown once, never twice.
  // The notice shows first and the gate's reason replaces it once the refetch lands, so the
  // element is looked up again on each try rather than held from the first find.
  await waitFor(() => expect(screen.getByText("A run is in progress")).toBeInTheDocument());
  await waitFor(() => expect(screen.getByRole("button", { name: "Run" })).toBeDisabled());
  expect(screen.getAllByText("A run is in progress")).toHaveLength(1);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("a 412 closes the dialog, says why and refreshes the target", async () => {
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.post(`${P}/run-requests`, () => {
      server.use(http.get(`${P}/ci-target`, () => HttpResponse.json({ ...TARGET, configured: false })));
      return HttpResponse.json({ detail: "Running tests from QEOS is not set up for this project" }, { status: 412 });
    }),
  );
  renderAt("/projects/42/cases/1");
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("not set up for this project");
  expect(await screen.findByRole("link", { name: "Configure in Settings" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Run" })).toBeDisabled();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("after a run starts, focus goes back to Run", async () => {
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.post(`${P}/run-requests`, () => HttpResponse.json(runRequest(), { status: 201 })),
  );
  renderAt("/projects/42/cases/1");
  const run = await screen.findByRole("button", { name: "Run" });
  await userEvent.click(run);
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(run).toHaveFocus();
});

test("a dialog left open closes for good when someone else starts a run", async () => {
  server.use(http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))));
  const qc = renderAt("/projects/42/cases/1");
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  server.use(http.get(`${P}/run-requests`, () => HttpResponse.json({ total: 1, items: [runRequest({ status: "running" })] })));
  await qc.invalidateQueries({ queryKey: ["run-requests", 42] });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  server.use(http.get(`${P}/run-requests`, () => HttpResponse.json({ total: 0, items: [] })));
  await qc.invalidateQueries({ queryKey: ["run-requests", 42] });
  await waitFor(() => expect(screen.getByRole("button", { name: "Run" })).toBeEnabled());
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("an empty suite says why Run suite is off", async () => {
  server.use(http.get(`${P}/suites/5`, () => HttpResponse.json({
    id: 5, name: "Smoke", description: null, case_count: 0, created_at: "2026-10-06T10:00:00Z", updated_at: null, cases: [] })));
  renderAt("/projects/42/suites/5");
  expect(await screen.findByText("This suite has no cases")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Run suite" })).toBeDisabled();
});

test("the selection survives a filter that shows no rows, and stays visible", async () => {
  server.use(http.get(`${P}/cases`, ({ request }) => {
    const sp = new URL(request.url).searchParams;
    return HttpResponse.json(sp.get("search") ? { total: 0, items: [] } : { total: 1, items: [kase(1)] });
  }));
  renderAt("/projects/42/cases?group=scenario");
  await userEvent.click(await screen.findByRole("checkbox", { name: "Select TC-1 Case 1" }));
  await userEvent.type(screen.getByRole("searchbox", { name: "Search" }), "zzz");
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(await screen.findByText("No test cases match these filters.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Run selected (1)" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Clear selection" })).toBeInTheDocument();
});

test("when the new run turns Play off during the start, focus still lands on the control", async () => {
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))),
    http.post(`${P}/run-requests`, () => {
      server.use(http.get(`${P}/run-requests`, () => HttpResponse.json({ total: 1, items: [runRequest({ status: "queued" })] })));
      return HttpResponse.json(runRequest(), { status: 201 });
    }),
  );
  renderAt("/projects/42/cases/1");
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  await waitFor(() => expect(screen.getByRole("button", { name: "Run" })).toBeDisabled());
  const box = screen.getByRole("button", { name: "Run" }).closest(".run-control");
  expect(document.activeElement).toBe(box);
});

test("with no rows left on the page, a started selection still leaves focus on the page's heading", async () => {
  server.use(
    http.get(`${P}/cases`, ({ request }) => {
      const sp = new URL(request.url).searchParams;
      return HttpResponse.json(sp.get("search") ? { total: 0, items: [] } : { total: 1, items: [kase(1)] });
    }),
    http.post(`${P}/run-requests`, () => HttpResponse.json(runRequest(), { status: 201 })),
  );
  renderAt("/projects/42/cases?group=scenario");
  await userEvent.click(await screen.findByRole("checkbox", { name: "Select TC-1 Case 1" }));
  await userEvent.type(screen.getByRole("searchbox", { name: "Search" }), "zzz");
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  await screen.findByText("No test cases match these filters.");
  await userEvent.click(screen.getByRole("button", { name: "Run selected (1)" }));
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: /Run selected/ })).not.toBeInTheDocument());
  expect(screen.getByRole("heading", { level: 1, name: "Test cases" })).toHaveFocus();
});

const suiteWith = (sourcePaths: (string | null)[]) => http.get(`${P}/suites/5`, () => HttpResponse.json({
  id: 5, name: "Smoke", description: null, case_count: sourcePaths.length, created_at: "2026-10-06T10:00:00Z", updated_at: null,
  cases: sourcePaths.map((source_path, i) => ({ number: i + 1, key: `TC-${i + 1}`, title: `Case ${i + 1}`, status: "draft",
    priority: "medium", labels: [], automated_test_key: null, source_path })) }));

test("a suite with manual cases says how many run and how many are skipped, and lists only the automated ones", async () => {
  let sent: unknown = null;
  server.use(suiteWith(["tests/a.feature", null, "tests/b.feature", null, null]),
    http.post(`${P}/run-requests`, async ({ request }) => { sent = await request.json(); return HttpResponse.json(runRequest(), { status: 201 }); }));
  renderAt("/projects/42/suites/5");
  await userEvent.click(await screen.findByRole("button", { name: "Run suite" }));
  const dialog = screen.getByRole("dialog", { name: "Run 2 automated cases (3 manual cases skipped)?" });
  expect(within(dialog).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["TC-1 · Case 1", "TC-3 · Case 3"]);
  await userEvent.click(within(dialog).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(sent).toEqual({ suite_id: 5 }));
});

test("one skipped manual case reads in the singular", async () => {
  server.use(suiteWith(["tests/a.feature", null]));
  renderAt("/projects/42/suites/5");
  await userEvent.click(await screen.findByRole("button", { name: "Run suite" }));
  expect(screen.getByRole("dialog", { name: "Run 1 automated case (1 manual case skipped)?" })).toBeInTheDocument();
});

test("a suite of manual cases only cannot run, and says why", async () => {
  server.use(suiteWith([null, null]));
  renderAt("/projects/42/suites/5");
  expect(await screen.findByText("This suite has no automated cases")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Run suite" })).toBeDisabled();
});

test("select-all is indeterminate while only some of the page is selected", async () => {
  listing(Array.from({ length: 3 }, (_, i) => kase(i + 1)));
  renderAt("/projects/42/cases?group=scenario");
  const all = await screen.findByRole("checkbox", { name: "Select all imported cases on this page" }) as HTMLInputElement;
  expect(all.indeterminate).toBe(false);
  await userEvent.click(screen.getByRole("checkbox", { name: "Select TC-1 Case 1" }));
  expect(all.indeterminate).toBe(true);
  expect(all.checked).toBe(false);
  await userEvent.click(all);
  expect(all.indeterminate).toBe(false);
  expect(all.checked).toBe(true);
  await userEvent.click(all);
  expect(all.indeterminate).toBe(false);
  expect(all.checked).toBe(false);
});

test("selecting a row inserts nothing above the table: the bar follows it and cannot push rows down", async () => {
  listing([kase(1), kase(2)]);
  renderAt("/projects/42/cases?group=scenario");
  const table = await screen.findByRole("region", { name: "Test cases" });
  // The header's New case link steps back from primary once a selection exists; that is a class, not layout
  const above = () => (table.parentElement as HTMLElement).innerHTML.split(table.outerHTML)[0].replace(/class="button( primary)?"/g, "");
  const before = above();
  await userEvent.click(screen.getByRole("checkbox", { name: "Select TC-1 Case 1" }));
  const bar = screen.getByRole("region", { name: "Selected cases" });
  expect(table.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(above()).toBe(before);
});

const primaries = () =>
  Array.from(document.querySelectorAll("button.primary, a.button.primary")).map((el) => (el.textContent ?? "").trim());

test("Cases: New case is the one primary until cases are selected; then Run selected is", async () => {
  listing([kase(1), kase(2)]);
  renderAt("/projects/42/cases?group=scenario");
  await screen.findByRole("checkbox", { name: "Select TC-1 Case 1" });
  expect(primaries()).toEqual(["New case"]);
  await userEvent.click(screen.getByRole("checkbox", { name: "Select TC-1 Case 1" }));
  expect(primaries()).toEqual(["Run selected (1)"]);
});

test("Cases: an empty list keeps one primary, the empty state's", async () => {
  renderAt("/projects/42/cases?group=scenario");
  await screen.findByText("No test cases yet");
  expect(primaries()).toEqual(["Write the first case"]);
});

test("Case detail: Run is primary while the form is clean, Save takes over once it is dirty", async () => {
  server.use(http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1))));
  renderAt("/projects/42/cases/1");
  await screen.findByRole("button", { name: "Run" });
  expect(primaries()).toEqual(["Run"]);
  await userEvent.selectOptions(screen.getByLabelText("Priority"), "high");
  expect(primaries()).toEqual(["Save changes"]);
});

test("Suite detail: Run suite is the one primary while nothing is unsaved", async () => {
  server.use(suiteWith(["tests/a.feature"]));
  renderAt("/projects/42/suites/5");
  await screen.findByRole("button", { name: "Run suite" });
  expect(primaries()).toEqual(["Run suite"]);
  await userEvent.click(screen.getByRole("button", { name: "Run suite" }));
  expect(primaries().sort()).toEqual(["Run"]); // the open question's Run; the trigger steps back
});

test("the sticky selection bar reserves its height so a focused row is not hidden under it", async () => {
  const offset = vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(80);
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  try {
    listing([kase(1), kase(2)]);
    renderAt("/projects/42/cases?group=scenario");
    expect(document.documentElement.style.scrollPaddingBottom).toBe("");
    await userEvent.click(await screen.findByRole("checkbox", { name: "Select TC-1 Case 1" }));
    await waitFor(() => expect(document.documentElement.style.scrollPaddingBottom).toBe("88px"));
    expect(screen.getByRole("region", { name: "Test cases" })).toHaveStyle({ paddingBottom: "80px" });
    // Tabbing to another row's checkbox scrolls it into view above the bar
    scrolled.mockClear();
    screen.getByRole("checkbox", { name: "Select TC-2 Case 2" }).focus();
    expect(scrolled).toHaveBeenCalledWith({ block: "nearest" });
    // No selection, no reserved space
    await userEvent.click(screen.getByRole("button", { name: "Clear selection" }));
    await waitFor(() => expect(document.documentElement.style.scrollPaddingBottom).toBe(""));
  } finally {
    offset.mockRestore();
    delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView;
  }
});
