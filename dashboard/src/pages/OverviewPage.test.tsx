import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import OverviewPage from "./OverviewPage";

const RUN = {
  id: 61, project_id: 42, ci_provider: "github_actions", ci_run_url: null, commit_sha: "abcdef1234567890",
  branch: "main", environment: "staging", agent_version: "0.1.0", commit_author: "Ada",
  commit_message: "fix(cart): keep totals stable", pr_number: null, base_branch: null,
  started_at: "2026-10-04T10:00:00Z", finished_at: "2026-10-04T10:04:00Z", duration_ms: 240000,
  total: 24, passed: 20, failed: 3, skipped: 0, errored: 1, change_base_ref: null, changed_files: null,
  additions: null, deletions: null, changes_truncated: null, created_at: "2026-10-04T10:05:00Z",
};

const failing = (status: string, name: string, message: string) => ({
  id: name.length, test_key: `k-${name}`, suite: "checkout", class_name: "Cart", name, status,
  duration_ms: 10, message, details: null, truncated: false, redacted: false, file: null, owner: null,
});

function detail(results: object[]) {
  return { ...RUN, results, changes: [], components: [] };
}

function mockProject({ runs = [RUN] }: { runs?: object[] } = {}) {
  server.use(
    http.get("/api/v1/projects/42/runs", () => HttpResponse.json(runs)),
    http.get("/api/v1/runs/61", ({ request }) => {
      const status = new URL(request.url).searchParams.get("status");
      if (status === "failed") return HttpResponse.json(detail([failing("failed", "pays with stored card", "AssertionError: 41.99 != 42.00\n  at cart.py:88")]));
      if (status === "errored") return HttpResponse.json(detail([failing("errored", "applies coupon", "TimeoutError")]));
      return HttpResponse.json(detail([]));
    }),
    http.get("/api/v1/projects/42/analytics/trends", () => HttpResponse.json({
      tz: "UTC", bucket: "week",
      days: [
        { date: "2026-09-21", runs: 10, total: 240, passed: 200, failed: 40, errored: 0, skipped: 0, pass_rate: 0.833, avg_run_duration_ms: 1, max_run_duration_ms: 1 },
        { date: "2026-09-28", runs: 12, total: 288, passed: 276, failed: 12, errored: 0, skipped: 0, pass_rate: 0.958, avg_run_duration_ms: 1, max_run_duration_ms: 1 },
      ],
    })),
    http.get("/api/v1/projects/42/analytics/flaky", () => HttpResponse.json([
      { test_key: "a", suite: "s", class_name: "c", name: "a", reason: "same_commit", commits: [], flips: null, flip_rate: null, runs: 9, last_status: "failed", last_seen: "2026-10-04T10:00:00Z" },
      { test_key: "b", suite: "s", class_name: "c", name: "b", reason: "flips", commits: [], flips: 4, flip_rate: 0.5, runs: 9, last_status: "passed", last_seen: "2026-10-04T10:00:00Z" },
      { test_key: "c", suite: "s", class_name: "c", name: "c", reason: "flips", commits: [], flips: 3, flip_rate: 0.4, runs: 8, last_status: "passed", last_seen: "2026-10-04T10:00:00Z" },
    ])),
  );
}

function renderPage() {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/overview"]}>
        <Routes>
          <Route path="/projects/:projectId/overview" element={<OverviewPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("the latest run leads, with its verdict in words and what broke", async () => {
  mockProject();
  renderPage();
  expect(await screen.findByText("Failed")).toBeInTheDocument();
  expect(screen.getByText(/fix\(cart\): keep totals stable/)).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: "pays with stored card" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "applies coupon" })).toBeInTheDocument();
  // only the first line of the failure message
  expect(screen.getByText("AssertionError: 41.99 != 42.00")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /open run #61/i })).toBeInTheDocument();
});

test("pass rate and flaky counts are the API's numbers, labelled honestly", async () => {
  mockProject();
  renderPage();
  expect(await screen.findByText("95.8%")).toBeInTheDocument(); // this week, as the API computed it
  expect(screen.getByText(/83\.3% the week before/)).toBeInTheDocument();
  expect(await screen.findByText(/1 confirmed/)).toBeInTheDocument();
  expect(screen.getByText(/2 suspected/)).toBeInTheDocument();
});

test("a project without runs explains the next step instead of empty cards", async () => {
  mockProject({ runs: [] });
  renderPage();
  expect(await screen.findByText(/no runs yet/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /set up an api key/i })).toHaveAttribute("href", "/projects/42/settings");
});
