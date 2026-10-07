import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import { RunRequest } from "../api/runRequests";
import RunPanel from "./RunPanel";

const P = "/api/v1/projects/42";
const member = (user_id: number, email: string) => ({ id: user_id, organization_id: 1, user_id, email, role: "member",
  status: "active", created_at: "2026-01-01T00:00:00Z", updated_at: null });
const req = (extra: Partial<RunRequest> = {}): RunRequest => ({
  id: 9, requested_by: 7, requested_at: new Date(Date.now() - 65_000).toISOString(),
  selection: [{ case_number: 1, path: "tests/features/a.feature", name: "A" }, { case_number: 2, path: "tests/features/a.feature", name: "B" }],
  case_count: 2, suite_id: null, status: "running", conclusion: null, github_run_id: 501,
  github_run_url: "https://github.com/Acme/OBT/actions/runs/501", stopped_by: null, stopped_at: null, error: null,
  checked_at: new Date().toISOString(), refreshing: true, skipped_manual: 0, ...extra,
});

function show(get: () => RunRequest[], role = "member", caseNumber?: number, withSibling = false) {
  setAccessToken("acc");
  server.use(
    http.get(P, () => HttpResponse.json({ id: 42, name: "Web", organization_id: 1, my_role: role })),
    http.get("/api/v1/organizations/1/members", () => HttpResponse.json([member(7, "ana@example.com"), member(8, "rui@example.com")])),
    http.get(`${P}/run-requests`, () => { const items = get(); return HttpResponse.json({ total: items.length, items }); }),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RunPanel projectId={42} caseNumber={caseNumber} />
        {withSibling && <RunPanel projectId={42} />}
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return qc;
}

/** Waits until the project (so the role) and the run requests have loaded. */
const loaded = (qc: QueryClient) => waitFor(() => {
  expect(qc.getQueryState(["project", 42])?.status).toBe("success");
  expect(qc.getQueryState(["run-requests", 42, "latest"])?.status).toBe("success");
});

const panel = () => screen.findByRole("status", { name: "Run from QA Vision" });

test.each([
  ["queued", req({ status: "queued" }), /^Queued$/],
  ["queued after a 204 dispatch (no run yet)", req({ status: "queued", github_run_id: null, github_run_url: null }), /^Queued$/],
  ["running", req(), /^Running · 2 tests · started by ana@example\.com · 1m \d\ds$/],
  ["passed", req({ status: "completed", conclusion: "success", refreshing: false }), /^Passed$/],
  ["failed", req({ status: "completed", conclusion: "failure", refreshing: false }), /^Failed$/],
  ["skipped", req({ status: "completed", conclusion: "skipped", refreshing: false }), /^Skipped$/],
  ["cancelled on GitHub", req({ status: "cancelled", conclusion: "cancelled", refreshing: false }), /^Cancelled$/],
  ["stopped", req({ status: "cancelled", conclusion: "cancelled", stopped_by: 8, refreshing: false }), /^Stopped by rui@example\.com$/],
  ["not started", req({ status: "failed_to_start", error: "The workflow did not start", github_run_id: null, github_run_url: null, refreshing: false }),
    /^Didn't start: The workflow did not start$/],
])("the panel reads %s", async (_, r, text) => {
  show(() => [r]);
  expect(await within(await panel()).findByText(text)).toBeInTheDocument();
});

test("View in GitHub opens the run", async () => {
  show(() => [req()]);
  expect(await within(await panel()).findByRole("link", { name: /view in github/i }))
    .toHaveAttribute("href", "https://github.com/Acme/OBT/actions/runs/501");
});

test("Stop asks first, then shows Stopping…", async () => {
  let stopped = false;
  let current = req();
  server.use(http.post(`${P}/run-requests/9/stop`, () => {
    stopped = true;
    current = req({ status: "cancelling", stopped_by: 7 });
    return HttpResponse.json(current);
  }));
  show(() => [current]);
  await userEvent.click(await screen.findByRole("button", { name: "Stop the run" }));
  expect(screen.getByText("Stop this run?")).toBeInTheDocument();
  expect(stopped).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Stop run" }));
  expect(await screen.findByText("Stopping…")).toBeInTheDocument();
  expect(stopped).toBe(true);
  expect(screen.queryByRole("button", { name: "Stop the run" })).not.toBeInTheDocument();
});

test("a Stop on a run that just finished (409) refreshes and shows the final state without an error", async () => {
  let current = req();
  server.use(http.post(`${P}/run-requests/9/stop`, () => {
    current = req({ status: "completed", conclusion: "success", refreshing: false });
    return HttpResponse.json({ detail: { code: "run_finished", message: "This run has already finished" } }, { status: 409 });
  }));
  show(() => [current]);
  await userEvent.click(await screen.findByRole("button", { name: "Stop the run" }));
  await userEvent.click(screen.getByRole("button", { name: "Stop run" }));
  expect(await screen.findByText("Passed")).toBeInTheDocument();
  expect(screen.queryByText("This run has already finished")).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("Stop is disabled while the request is on its way, so a double click stops once", async () => {
  let calls = 0;
  let release: () => void = () => undefined;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  server.use(http.post(`${P}/run-requests/9/stop`, async () => {
    calls += 1;
    await gate;
    return HttpResponse.json(req({ status: "cancelling", stopped_by: 7 }));
  }));
  show(() => [req()]);
  await userEvent.click(await screen.findByRole("button", { name: "Stop the run" }));
  await userEvent.dblClick(screen.getByRole("button", { name: "Stop run" }));
  expect(await screen.findByText("Stopping…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Stop the run" })).toBeDisabled();
  release();
  await waitFor(() => expect(calls).toBe(1));
});

test.each(["owner", "admin", "member"])("a %s sees Stop", async (role) => {
  show(() => [req()], role);
  expect(await screen.findByRole("button", { name: "Stop the run" })).toBeInTheDocument();
});

test.each(["viewer", "billing_manager"])("a %s sees the state but no Stop", async (role) => {
  const qc = show(() => [req()], role);
  await within(await panel()).findByText(/started by ana@example\.com/);
  await loaded(qc);
  expect(screen.queryByRole("button", { name: "Stop the run" })).not.toBeInTheDocument();
});

test("the panel polls every 5 s while the request is active and stops when it ends", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    let calls = 0;
    show(() => { calls += 1; return [calls === 1 ? req() : req({ status: "completed", conclusion: "failure", refreshing: false })]; });
    expect(await screen.findByText(/^Running/)).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(5_000));
    expect(await screen.findByText("Failed")).toBeInTheDocument();
    const after = calls;
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    expect(calls).toBe(after);
  } finally {
    vi.useRealTimers();
  }
});

test("a finished run links to its results, matching the CI URL whatever its case", async () => {
  server.use(http.get(`${P}/runs`, () => HttpResponse.json([
    { id: 76, ci_run_url: "https://github.com/acme/obt/actions/runs/500" },
    { id: 77, ci_run_url: "https://github.com/acme/obt/actions/runs/501" }])));
  show(() => [req({ status: "completed", conclusion: "success", refreshing: false })]);
  expect(await screen.findByRole("link", { name: "Open the results (run #77)" })).toHaveAttribute("href", "/projects/42/runs/77");
});

test("until results arrive the panel waits for them", async () => {
  show(() => [req({ status: "completed", conclusion: "success", refreshing: false })]);
  expect(await screen.findByText("Waiting for results…")).toBeInTheDocument();
  expect(screen.queryByText(/Results not received/)).not.toBeInTheDocument();
});

test("5 minutes after the end, with no other update, it points at the upload step", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    show(() => [req({ status: "completed", conclusion: "success", refreshing: false,
      checked_at: new Date(Date.now() - 4 * 60_000).toISOString() })]);
    expect(await screen.findByText("Waiting for results…")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(90_000));
    expect(await screen.findByText("Results not received: check the QA Vision upload step")).toBeInTheDocument();
    expect(screen.queryByText("Waiting for results…")).not.toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});

test("after 5 minutes without results it points at the upload step", async () => {
  show(() => [req({ status: "completed", conclusion: "success", refreshing: false,
    checked_at: new Date(Date.now() - 6 * 60_000).toISOString() })]);
  expect(await screen.findByText("Results not received: check the QA Vision upload step")).toBeInTheDocument();
});

test.each([
  ["stopped", req({ status: "cancelled", conclusion: "cancelled", stopped_by: 8, refreshing: false, checked_at: new Date(Date.now() - 6 * 60_000).toISOString() })],
  ["cancelled", req({ status: "cancelled", conclusion: "cancelled", refreshing: false })],
  ["not started", req({ status: "failed_to_start", error: "x", github_run_id: null, github_run_url: null, refreshing: false })],
])("a %s run never waits for results", async (_, r) => {
  const qc = show(() => [r]);
  await panel();
  await loaded(qc);
  expect(screen.queryByText(/results/i)).not.toBeInTheDocument();
});

test("on a case detail the panel does not show a case outside the active request", async () => {
  // The sibling panel (whole project) proves the request and the names have loaded
  const qc = show(() => [req()], "member", 3, true);
  const panels = await screen.findAllByRole("status", { name: "Run from QA Vision" });
  await loaded(qc);
  expect(panels).toHaveLength(1);
  expect(screen.getAllByRole("status", { name: "Run from QA Vision" })).toHaveLength(1);
});

test("on a case detail of a selected case the panel shows", async () => {
  show(() => [req()], "member", 2);
  expect(await panel()).toBeInTheDocument();
});

test("on a case detail the panel hides once the run has ended", async () => {
  const qc = show(() => [req({ status: "completed", conclusion: "success", refreshing: false })], "member", 2, true);
  await screen.findByText("Passed");
  await loaded(qc);
  expect(screen.getAllByRole("status", { name: "Run from QA Vision" })).toHaveLength(1);
});

const soon = () => new Date(Date.now() + 3 * 86_400_000).toISOString();
const expiring = () => http.get(`${P}/ci-target`, () => HttpResponse.json({ available: true, configured: true, provider: "github",
  repo: "acme/obt", workflow: "qa-vision-run.yml", ref: "main", token_last4: "a1b2", token_expires_at: soon(),
  updated_at: null, last_change: null }));
const EXPIRY = /^The GitHub token expires on .+\. Replace it in Settings$/;

test.each(["owner", "admin"])("a %s sees the expiry warning", async (role) => {
  server.use(expiring());
  show(() => [], role);
  expect(await screen.findByText(EXPIRY)).toBeInTheDocument();
});

test.each(["member", "viewer"])("a %s does not see the expiry warning", async (role) => {
  server.use(expiring());
  const qc = show(() => [], role);
  await waitFor(() => expect(qc.getQueryState(["ci-target", 42])?.status).toBe("success"));
  await loaded(qc);
  expect(screen.queryByText(EXPIRY)).not.toBeInTheDocument();
});

const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

test("a stale active request shows why, under the state", async () => {
  show(() => [req({ error: "token invalid or expired" })]);
  expect(await within(await panel()).findByText("GitHub: token invalid or expired")).toBeInTheDocument();
});

test("an active request with no error shows no GitHub line", async () => {
  const qc = show(() => [req()]);
  await within(await panel()).findByText(/^Running/);
  await loaded(qc);
  expect(screen.queryByText(/^GitHub:/)).not.toBeInTheDocument();
});

test("a request that ended because the run left GitHub says why", async () => {
  show(() => [req({ status: "cancelled", conclusion: "cancelled", refreshing: false, error: "The run is no longer on GitHub" })]);
  expect(await within(await panel()).findByText("Cancelled: The run is no longer on GitHub")).toBeInTheDocument();
});

test("a run longer than 60 minutes stays visible after it ends, measured from the end", async () => {
  show(() => [req({ requested_at: ago(90), status: "completed", conclusion: "success", refreshing: false, checked_at: ago(1) })]);
  expect(await within(await panel()).findByText("Passed")).toBeInTheDocument();
});

test("an ended run disappears 60 minutes after the end", async () => {
  const qc = show(() => [req({ requested_at: ago(200), status: "completed", conclusion: "success", refreshing: false, checked_at: ago(61) })], "member", undefined, true);
  await loaded(qc);
  await waitFor(() => expect(qc.getQueryState(["project", 42])?.status).toBe("success"));
  expect(screen.queryByRole("status", { name: "Run from QA Vision" })).not.toBeInTheDocument();
});

test("a stopped run is measured from the later of stopped_at and checked_at", async () => {
  show(() => [req({ requested_at: ago(120), status: "cancelled", conclusion: "cancelled", stopped_by: 8, refreshing: false,
    stopped_at: ago(2), checked_at: ago(100) })]);
  expect(await within(await panel()).findByText("Stopped by rui@example.com")).toBeInTheDocument();
});

test("the panel polls no sooner than every 5 s", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    let calls = 0;
    show(() => { calls += 1; return [req()]; });
    expect(await screen.findByText(/^Running/)).toBeInTheDocument();
    const first = calls;
    await act(() => vi.advanceTimersByTimeAsync(4_000));
    expect(calls).toBe(first);
    await act(() => vi.advanceTimersByTimeAsync(1_500));
    await waitFor(() => expect(calls).toBeGreaterThan(first));
  } finally {
    vi.useRealTimers();
  }
});

test("the elapsed time is hidden from screen readers and the live text changes only with the status", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    const fixed = req(); // one request: a fresh one per poll would restart the elapsed time
    show(() => [fixed]);
    const region = await panel();
    const elapsed = await within(region).findByText(/1m \d\ds$/);
    expect(elapsed).toHaveAttribute("aria-hidden", "true");
    const live = region.querySelector(".sr-only:not(a *)") as HTMLElement;
    const before = live.textContent;
    const elapsedBefore = elapsed.textContent;
    expect(before).toMatch(/2 tests/);
    expect(before).not.toMatch(/\ds/);
    await act(() => vi.advanceTimersByTimeAsync(31_000));
    expect(region.querySelector(".sr-only:not(a *)")?.textContent).toBe(before);
    expect(within(region).getByText(/1m \d\ds$/).textContent).not.toBe(elapsedBefore);
  } finally {
    vi.useRealTimers();
  }
});

test("the results lookup asks only for GitHub Actions runs", async () => {
  let query = "";
  server.use(http.get(`${P}/runs`, ({ request }) => { query = new URL(request.url).search; return HttpResponse.json([]); }));
  show(() => [req({ status: "completed", conclusion: "success", refreshing: false })]);
  await waitFor(() => expect(query).toContain("ci_provider=github_actions"));
});
