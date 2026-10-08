import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { delay, http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import CasesPage from "./CasesPage";
import CaseEditorPage from "./CaseEditorPage";
import SuiteDetailPage from "./SuiteDetailPage";
import RequestedRunsPage from "./RequestedRunsPage";

// Suite duration prediction: the estimate in the Play dialog, the selection bar, the suite header and Requested runs

const P = "/api/v1/projects/42";
const MIN = 60_000;
const KEY = (n: number) => String(n).padStart(64, "a");
const TARGET = { available: true, configured: true, provider: "github", repo: "acme/obt", workflow: "qeos-run.yml",
  ref: "main", token_last4: "a1b2", token_expires_at: null, updated_at: "2026-10-07T10:00:00Z", last_change: null };

const kase = (number: number, extra: object = {}) => ({
  number, key: `TC-${number}`, title: `Case ${number}`, description: null, steps: [], labels: [], priority: "medium",
  status: "draft", automated_test_key: KEY(number), automated_name: null, created_by: 1, created_at: "2026-10-06T10:00:00Z",
  updated_by: null, updated_at: null, suites: [], source_path: "tests/features/a.feature", gherkin: "Scenario: x",
  feature_name: "A", ...extra,
});

const runRequest = (extra: object = {}) => ({
  id: 9, requested_by: 7, requested_at: new Date().toISOString(),
  selection: [{ case_number: 1, path: "tests/features/a.feature", name: "Case 1" }], case_count: 1, suite_id: null,
  status: "queued", conclusion: null, github_run_id: 501, github_run_url: "https://github.com/acme/obt/actions/runs/501",
  stopped_by: null, stopped_at: null, error: null, checked_at: null, refreshing: true, skipped_manual: 0,
  estimate_ms: null, estimate_upper_ms: null, ...extra,
});

const estimate = (estimate_ms: number | null, upper_ms: number | null, without = 0) => ({
  estimate_ms, upper_ms, tests_with_history: estimate_ms === null ? 0 : 1, tests_without_history: without,
  environment_used: 0, model: { overhead_ms: 0, factor: 1, runs: 5, fitted: true },
});

/** Answers every estimate with `body` (or `status`), recording what each asked. */
function estimates(body: object | null, opts: { status?: number; wait?: "infinite" } = {}) {
  const asked: string[][] = [];
  server.use(http.post(`${P}/analytics/duration-estimate`, async ({ request }) => {
    asked.push(((await request.json()) as { test_keys: string[] }).test_keys);
    if (opts.wait) await delay(opts.wait);
    if (opts.status) return HttpResponse.json({ detail: "boom" }, { status: opts.status });
    return HttpResponse.json(body);
  }));
  return asked;
}

function playRecorder() {
  const sent: unknown[] = [];
  server.use(http.post(`${P}/run-requests`, async ({ request }) => {
    sent.push(await request.json());
    return HttpResponse.json(runRequest(), { status: 201 });
  }));
  return sent;
}

beforeEach(() => {
  server.use(
    http.get(P, () => HttpResponse.json({ id: 42, organization_id: 1, name: "Web", my_role: "member" })),
    http.get(`${P}/case-features`, () => HttpResponse.json([])),
    http.get(`${P}/case-folders`, () => HttpResponse.json([])),
    http.get(`${P}/case-labels`, () => HttpResponse.json([])),
    http.get(`${P}/cases`, () => HttpResponse.json({ total: 0, items: [] })),
    http.get(`${P}/ci-target`, () => HttpResponse.json(TARGET)),
    http.get(`${P}/run-requests`, () => HttpResponse.json({ total: 0, items: [] })),
    http.get(`${P}/history/*`, () => HttpResponse.json({})),
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
          <Route path="/projects/:projectId/runs/requested" element={<RequestedRunsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function caseDetail(extra: object = {}) {
  server.use(
    http.get(`${P}/cases/1`, () => HttpResponse.json(kase(1, extra))),
    http.get(`${P}/analytics/tests/:key/history`, () => HttpResponse.json({ test_key: KEY(1), suite: "", class_name: "", name: "x",
      summary: { runs: 0, passed: 0, failed: 0, errored: 0, skipped: 0, pass_rate: null, avg_duration_ms: null }, executions: [] })),
  );
  renderAt("/projects/42/cases/1");
}

test("the Play dialog shows the estimate and Run stores it on the request", async () => {
  const asked = estimates(estimate(12 * MIN, 15 * MIN));
  const sent = playRecorder();
  caseDetail();
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  const dialog = screen.getByRole("dialog", { name: "Run 1 test?" });
  expect(await within(dialog).findByText("Estimated duration ≈ 12 min (up to 15 min)")).toBeInTheDocument();
  expect(asked).toEqual([[KEY(1)]]);
  await userEvent.click(within(dialog).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(sent).toEqual([{ case_numbers: [1], estimate_ms: 12 * MIN, estimate_upper_ms: 15 * MIN }]));
});

test("with no history at all the dialog says so", async () => {
  estimates(estimate(null, null, 1));
  caseDetail();
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  const dialog = screen.getByRole("dialog", { name: "Run 1 test?" });
  expect(await within(dialog).findByText("No history to estimate yet")).toBeInTheDocument();
});

test("an estimate that fails leaves no line, and Play still starts without one", async () => {
  estimates(null, { status: 500 });
  const sent = playRecorder();
  caseDetail();
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  const dialog = screen.getByRole("dialog", { name: "Run 1 test?" });
  await waitFor(() => expect(within(dialog).queryByRole("status", { name: "Estimating duration" })).not.toBeInTheDocument());
  expect(within(dialog).queryByText(/Estimated duration/)).not.toBeInTheDocument();
  expect(within(dialog).queryByRole("alert")).not.toBeInTheDocument();
  await userEvent.click(within(dialog).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(sent).toEqual([{ case_numbers: [1] }]));
});

test("while the estimate loads the dialog shows a placeholder and Run is never held back", async () => {
  estimates(null, { wait: "infinite" });
  const sent = playRecorder();
  caseDetail();
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  const dialog = screen.getByRole("dialog", { name: "Run 1 test?" });
  expect(await within(dialog).findByRole("status", { name: "Estimating duration" })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Run" })).toBeEnabled();
  await userEvent.click(within(dialog).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(sent).toEqual([{ case_numbers: [1] }]));
});

test("an unlinked case asks for no estimate", async () => {
  const asked = estimates(estimate(MIN, MIN));
  caseDetail({ automated_test_key: null });
  await userEvent.click(await screen.findByRole("button", { name: "Run" }));
  expect(screen.getByRole("dialog", { name: "Run 1 test?" })).toBeInTheDocument();
  expect(screen.queryByText(/Estimated duration/)).not.toBeInTheDocument();
  expect(asked).toEqual([]);
});

function listing(items: object[]) {
  server.use(http.get(`${P}/cases`, () => HttpResponse.json({ total: items.length, items })));
}

// The debounce runs on a fake clock that only moves when the test says so (plus real time for msw and React Query):
// the checkbox clicks are synchronous fireEvents, so no time can pass between them however slow the machine is.
function fakeClock() {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}
afterEach(() => vi.useRealTimers());
const settle = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });

test("the selection bar totals the selection once it settles, asking once for a quick run of clicks", async () => {
  listing([kase(1), kase(2), kase(3, { automated_test_key: null })]);
  const asked = estimates(estimate(6 * MIN, 8 * MIN));
  renderAt("/projects/42/cases?group=scenario");
  const first = await screen.findByRole("checkbox", { name: "Select TC-1 Case 1" });
  const user = fakeClock();
  fireEvent.click(first);
  fireEvent.click(screen.getByRole("checkbox", { name: "Select TC-2 Case 2" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Select TC-3 Case 3" }));
  const bar = screen.getByRole("region", { name: "Selected cases" });
  await settle(399);
  expect(within(bar).queryByText(/≈/)).not.toBeInTheDocument();
  await settle(1);
  expect(await within(bar).findByText("· ≈ 6 min")).toBeInTheDocument();
  expect(asked).toEqual([[KEY(1), KEY(2)]]); // one request, after the burst, for the linked keys only
  // The dialog reuses the bar's answer (same sorted keys): no second request. TC-3 has no test: it counts as without history
  await user.click(within(bar).getByRole("button", { name: "Run selected (3)" }));
  expect(await within(bar).findByText("Estimated duration ≈ 6 min (up to 8 min) · 1 test without history")).toBeInTheDocument();
  expect(asked).toHaveLength(1);
});

test("the selection bar keeps the last total while the next one loads", async () => {
  listing([kase(1), kase(2)]);
  let release: () => void = () => {};
  const held = new Promise<void>((r) => { release = r; });
  const asked: string[][] = [];
  server.use(http.post(`${P}/analytics/duration-estimate`, async ({ request }) => {
    const keys = ((await request.json()) as { test_keys: string[] }).test_keys;
    asked.push(keys);
    if (keys.length === 1) return HttpResponse.json(estimate(6 * MIN, 6 * MIN));
    await held;
    return HttpResponse.json(estimate(9 * MIN, 9 * MIN));
  }));
  renderAt("/projects/42/cases?group=scenario");
  const first = await screen.findByRole("checkbox", { name: "Select TC-1 Case 1" });
  fakeClock();
  fireEvent.click(first);
  await settle(400);
  const bar = screen.getByRole("region", { name: "Selected cases" });
  expect(await within(bar).findByText("· ≈ 6 min")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: "Select TC-2 Case 2" }));
  await settle(400);
  await waitFor(() => expect(asked).toHaveLength(2)); // the next answer is on its way, and held
  expect(within(bar).getByText("· ≈ 6 min")).toBeInTheDocument();
  release();
  expect(await within(bar).findByText("· ≈ 9 min")).toBeInTheDocument();
});

test("a selection with no linked case shows no total", async () => {
  listing([kase(1, { automated_test_key: null })]);
  const asked = estimates(estimate(MIN, MIN));
  renderAt("/projects/42/cases?group=scenario");
  const first = await screen.findByRole("checkbox", { name: "Select TC-1 Case 1" });
  fakeClock();
  fireEvent.click(first);
  await settle(1000);
  await act(async () => {}); // let any request that would have started reach the server
  expect(screen.queryByText(/≈/)).not.toBeInTheDocument();
  expect(asked).toEqual([]);
});

function suite(cases: object[]) {
  server.use(http.get(`${P}/suites/5`, () => HttpResponse.json({
    id: 5, name: "Smoke", description: null, case_count: cases.length, created_at: "2026-10-06T10:00:00Z", updated_at: null, cases })));
}
const suiteCase = (n: number, extra: object = {}) => ({ number: n, key: `TC-${n}`, title: `Case ${n}`, status: "draft",
  priority: "medium", labels: [], automated_test_key: KEY(n), source_path: "a.feature", ...extra });

test("suite detail shows the estimate in its header, from its automated cases, and Run suite stores it", async () => {
  suite([suiteCase(1), suiteCase(2), suiteCase(3, { source_path: null, automated_test_key: null })]);
  const asked = estimates(estimate(100 * MIN, 120 * MIN, 1));
  const sent = playRecorder();
  renderAt("/projects/42/suites/5");
  expect(await screen.findByText("Estimated duration ≈ 1 h 40 min (up to 2 h) · 1 test without history")).toBeInTheDocument();
  expect(asked[0]).toEqual([KEY(1), KEY(2)]);
  await userEvent.click(screen.getByRole("button", { name: "Run suite" }));
  const dialog = screen.getByRole("dialog");
  await userEvent.click(within(dialog).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(sent).toEqual([{ suite_id: 5, estimate_ms: 100 * MIN, estimate_upper_ms: 120 * MIN }]));
});

test("automated cases with no linked test count as without history, on top of what the server reports", async () => {
  // 5 automated cases, 2 of them unlinked; the server knows no history for 1 of the 3 it was asked about
  suite([suiteCase(1), suiteCase(2), suiteCase(3), suiteCase(4, { automated_test_key: null }), suiteCase(5, { automated_test_key: null })]);
  const asked = estimates(estimate(12 * MIN, 15 * MIN, 1));
  renderAt("/projects/42/suites/5");
  expect(await screen.findByText("Estimated duration ≈ 12 min (up to 15 min) · 3 tests without history")).toBeInTheDocument();
  expect(asked[0]).toEqual([KEY(1), KEY(2), KEY(3)]);
});

test("a suite with no linked case shows no estimate", async () => {
  suite([suiteCase(1, { automated_test_key: null })]);
  const asked = estimates(estimate(MIN, MIN));
  renderAt("/projects/42/suites/5");
  expect(await screen.findByRole("button", { name: "Run suite" })).toBeInTheDocument();
  expect(screen.queryByText(/Estimated duration/)).not.toBeInTheDocument();
  expect(asked).toEqual([]);
});

const ago = (minutes: number) => new Date(Date.now() - minutes * MIN).toISOString();

test("Requested runs: time left while running, longer than estimated, estimate against actual, nothing for old requests", async () => {
  server.use(http.get(`${P}/run-requests`, () => HttpResponse.json({ total: 4, items: [
    runRequest({ id: 4, status: "running", requested_at: ago(6), estimate_ms: 10 * MIN, estimate_upper_ms: 12 * MIN }),
    runRequest({ id: 3, status: "running", requested_at: ago(20), refreshing: true, estimate_ms: 10 * MIN, estimate_upper_ms: 12 * MIN }),
    runRequest({ id: 2, status: "completed", conclusion: "success", refreshing: false, requested_at: "2026-10-07T10:00:00Z",
      checked_at: "2026-10-07T10:14:00Z", estimate_ms: 12 * MIN, estimate_upper_ms: 15 * MIN }),
    runRequest({ id: 1, status: "completed", conclusion: "success", refreshing: false, requested_at: "2026-10-06T10:00:00Z",
      checked_at: "2026-10-06T10:14:00Z" }),
  ] })));
  renderAt("/projects/42/runs/requested");
  const rows = await screen.findAllByRole("row");
  expect(rows).toHaveLength(5);
  expect(within(rows[1]).getByText("≈ 4 min left")).toBeInTheDocument();
  expect(within(rows[2]).getByText("running longer than estimated")).toBeInTheDocument();
  expect(within(rows[3]).getByText("estimated 12 min · took 14 min")).toBeInTheDocument();
  expect(within(rows[4]).queryByText(/estimated|left/)).not.toBeInTheDocument();
});

test("Requested runs: took is the matched QEOS run's own duration, not when the end was seen", async () => {
  const url = "https://github.com/acme/obt/actions/runs/700";
  server.use(
    http.get(`${P}/run-requests`, () => HttpResponse.json({ total: 1, items: [
      runRequest({ id: 7, status: "completed", conclusion: "success", refreshing: false, requested_at: "2026-10-07T10:00:00Z",
        checked_at: "2026-10-07T13:00:00Z", github_run_url: url, estimate_ms: 12 * MIN, estimate_upper_ms: 15 * MIN }),
    ] })),
    http.get(`${P}/runs`, () => HttpResponse.json([{ id: 70, ci_run_url: url, started_at: "2026-10-07T10:02:00Z",
      finished_at: "2026-10-07T10:15:00Z", duration_ms: 13 * MIN }])),
  );
  renderAt("/projects/42/runs/requested");
  expect(await screen.findByText("estimated 12 min · took 13 min")).toBeInTheDocument();
});

test("the dialog never stores the previous selection's estimate while the new one loads", async () => {
  listing([kase(1), kase(2)]);
  let slow = false;
  server.use(http.post(`${P}/analytics/duration-estimate`, async () => {
    if (slow) await delay("infinite");
    return HttpResponse.json(estimate(6 * MIN, 8 * MIN));
  }));
  const sent = playRecorder();
  renderAt("/projects/42/cases?group=scenario");
  await userEvent.click(await screen.findByRole("checkbox", { name: "Select TC-1 Case 1" }));
  const bar = screen.getByRole("region", { name: "Selected cases" });
  expect(await within(bar).findByText("· ≈ 6 min")).toBeInTheDocument();
  slow = true;
  await userEvent.click(screen.getByRole("checkbox", { name: "Select TC-2 Case 2" }));
  await userEvent.click(within(bar).getByRole("button", { name: "Run selected (2)" }));
  const dialog = screen.getByRole("dialog", { name: "Run 2 tests?" });
  expect(within(dialog).getByRole("status", { name: "Estimating duration" })).toBeInTheDocument();
  expect(within(dialog).queryByText(/Estimated duration/)).not.toBeInTheDocument();
  await userEvent.click(within(dialog).getByRole("button", { name: "Run" }));
  await waitFor(() => expect(sent).toEqual([{ case_numbers: [1, 2] }]));
});
