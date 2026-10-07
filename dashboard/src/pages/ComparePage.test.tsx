import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import ComparePage from "./ComparePage";

const run = (id: number, extra: object = {}) => ({
  id, project_id: 42, ci_provider: "github_actions", ci_run_url: null, commit_sha: `${id}bcdef1234`,
  branch: "main", environment: null, agent_version: null, commit_author: null, commit_message: null,
  pr_number: null, base_branch: null, started_at: "2026-10-01T12:00:00Z", finished_at: "2026-10-01T12:04:00Z",
  duration_ms: 240000, total: 10, passed: 8, failed: 2, skipped: 0, errored: 0, change_base_ref: null,
  changed_files: null, additions: null, deletions: null, changes_truncated: null, created_at: "2026-10-01T12:05:00Z",
  ...extra,
});

const item = (name: string, extra: object = {}) => ({
  test_key: `k-${name}`, suite: "checkout", class_name: "Cart", name, base_status: "passed", head_status: "failed",
  base_duration_ms: 100, head_duration_ms: 120, message: null, ...extra,
});

function comparison() {
  return {
    base: run(60), head: run(61),
    counts: { new_failures: 1, fixed: 1, still_failing: 0, slower: 1, added: 0, removed: 0, unchanged: 7 },
    new_failures: [item("pays with card", { message: "TimeoutError: waiting for #pay" })],
    fixed: [item("applies coupon", { base_status: "failed", head_status: "passed" })],
    still_failing: [],
    slower: [item("loads cart", { head_status: "passed", base_duration_ms: 1000, head_duration_ms: 4200 })],
    added: [], removed: [],
  };
}

function Location() {
  return <output data-testid="path">{useLocation().pathname}</output>;
}

function renderPage(url = "/projects/42/runs/61/compare/60") {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/projects/:projectId/runs/:runId/compare/:baseId" element={<><ComparePage /><Location /></>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("summarises what changed and lists each kind of change", async () => {
  server.use(http.get("/api/v1/runs/61/compare/60", () => HttpResponse.json(comparison())));
  renderPage();
  expect(await screen.findByRole("heading", { name: /run #61 compared with #60/i })).toBeInTheDocument();
  expect(await screen.findByText(/1 new failure\b/)).toBeInTheDocument();
  expect(screen.getByText(/7 unchanged/)).toBeInTheDocument();
  const broke = screen.getByRole("region", { name: /new failures/i });
  expect(within(broke).getByRole("link", { name: "pays with card" })).toHaveAttribute("href", "/projects/42/tests/k-pays%20with%20card");
  // The message is also in the narrow-screen line under the test name
  expect(within(broke).getAllByText("TimeoutError: waiting for #pay")).toHaveLength(2);
  expect(within(screen.getByRole("region", { name: /fixed/i })).getByText("applies coupon")).toBeInTheDocument();
  const slower = screen.getByRole("region", { name: /slower/i });
  expect(within(slower).getByText("+3.2 s")).toBeInTheDocument();
  // Empty kinds are left out rather than shown empty
  expect(screen.queryByRole("region", { name: /still failing/i })).not.toBeInTheDocument();
});

test("another base run can be chosen", async () => {
  server.use(
    http.get("/api/v1/runs/61/compare/60", () => HttpResponse.json(comparison())),
    http.get("/api/v1/runs/61/compare/55", () => HttpResponse.json({ ...comparison(), base: run(55) })),
  );
  renderPage();
  const field = await screen.findByLabelText(/compare with run/i);
  await userEvent.clear(field);
  await userEvent.type(field, "55");
  await userEvent.click(screen.getByRole("button", { name: /^compare$/i }));
  expect(screen.getByTestId("path")).toHaveTextContent("/projects/42/runs/61/compare/55");
  expect(await screen.findByRole("heading", { name: /compared with #55/i })).toBeInTheDocument();
});

test("runs that cannot be compared say so", async () => {
  server.use(http.get("/api/v1/runs/61/compare/60", () => HttpResponse.json({ detail: "Run not found" }, { status: 404 })));
  renderPage();
  expect(await screen.findByText(/run not found/i)).toBeInTheDocument();
});

test("the failure message is under the test name for phones", async () => {
  server.use(http.get("/api/v1/runs/61/compare/60", () => HttpResponse.json(comparison())));
  renderPage();
  const broke = await screen.findByRole("region", { name: /new failures/i });
  const meta = within(broke).getByRole("link", { name: "pays with card" }).closest("td")!.querySelector(".narrow-meta")!;
  expect(meta).toHaveTextContent("Message TimeoutError: waiting for #pay");
});
