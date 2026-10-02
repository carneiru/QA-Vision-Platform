import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import RunDetailPage from "./RunDetailPage";

const detail = (results: object[]) => ({
  id: 61, project_id: 42, ci_provider: "github_actions",
  ci_run_url: "https://ci.example/run/61", commit_sha: "abcdef1234567890",
  branch: "main", environment: "ci", agent_version: "0.1.0",
  started_at: "2026-10-01T12:00:00Z", finished_at: "2026-10-01T12:04:00Z",
  duration_ms: 240000, total: 24, passed: 20, failed: 3, skipped: 0, errored: 1,
  created_at: "2026-10-01T12:05:00Z",
  change_base_ref: null, changed_files: null, additions: null, deletions: null,
  changes_truncated: null, changes: [], results,
});

const result = {
  id: 1, test_key: "tests/a.py::TestLogin::test_ok", suite: "auth",
  class_name: "TestLogin", name: "test_ok", status: "failed", duration_ms: 480,
  message: "AssertionError: boom", details: null, truncated: true, redacted: false,
  file: "tests/a.py",
};

function renderDetail() {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/runs/61"]}>
        <Routes>
          <Route path="/projects/:projectId/runs/:runId" element={<RunDetailPage />} />
          <Route path="/projects/:projectId/tests/:testKey" element={<div>HISTORY</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders run metadata, truncated badge, and links to test history", async () => {
  server.use(http.get("/api/v1/runs/61", () => HttpResponse.json(detail([result]))));
  renderDetail();
  expect(await screen.findByText("abcdef1")).toBeInTheDocument();
  expect(screen.getByText(/truncated/i)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "test_ok" }));
  expect(await screen.findByText("HISTORY")).toBeInTheDocument();
});

test("status filter refetches server-side", async () => {
  const statuses: (string | null)[] = [];
  server.use(
    http.get("/api/v1/runs/61", ({ request }) => {
      statuses.push(new URL(request.url).searchParams.get("status"));
      return HttpResponse.json(detail([]));
    }),
  );
  renderDetail();
  await screen.findByText(/no results/i);
  await userEvent.selectOptions(screen.getByLabelText(/status/i), "failed");
  await screen.findByText(/no failed results/i);
  expect(statuses[statuses.length - 1]).toBe("failed");
  expect(statuses[0]).toBeNull();
});


test("a run with change data shows the Changes card and file list", async () => {
  const withChanges = {
    ...detail([]),
    change_base_ref: "origin/main", changed_files: 2, additions: 12, deletions: 3,
    changes_truncated: true,
    changes: [
      { path: "src/app.py", status: "M", additions: 12, deletions: 3 },
      { path: "assets/logo.png", status: "A", additions: null, deletions: null },
    ],
  };
  server.use(http.get("/api/v1/runs/61", () => HttpResponse.json(withChanges)));
  renderDetail();
  expect(await screen.findByText("src/app.py")).toBeInTheDocument();
  expect(screen.getByText(/\+12\s*−3 vs origin\/main/)).toBeInTheDocument();
  expect(screen.getByText(/list truncated/i)).toBeInTheDocument();
});

test("a run without change data shows no Changes card", async () => {
  server.use(http.get("/api/v1/runs/61", () => HttpResponse.json(detail([]))));
  renderDetail();
  await screen.findByText(/run #61/i);
  expect(screen.queryByText(/changes/i)).not.toBeInTheDocument();
});
