import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import RunsPage from "./RunsPage";

const run = (id: number) => ({
  id, project_id: 42, ci_provider: "github_actions",
  ci_run_url: "https://ci.example/run/" + id, commit_sha: "abcdef1234567890",
  branch: "main", environment: "ci", agent_version: "0.1.0",
  started_at: "2026-10-01T12:00:00Z", finished_at: "2026-10-01T12:04:00Z",
  duration_ms: 240000, total: 24, passed: 20, failed: 3, skipped: 0, errored: 1,
  created_at: "2026-10-01T12:05:00Z",
});

function renderRuns() {
  setTokens("acc", "ref");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/runs"]}>
        <Routes>
          <Route path="/projects/:projectId/runs" element={<RunsPage />} />
          <Route path="/projects/:projectId/runs/:runId" element={<div>RUN DETAIL</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders runs; clicking a run opens its detail", async () => {
  server.use(
    http.get("/api/v1/projects/42/runs", () => HttpResponse.json([run(61)])),
  );
  renderRuns();
  await userEvent.click(await screen.findByRole("link", { name: /#61/ }));
  expect(await screen.findByText("RUN DETAIL")).toBeInTheDocument();
});

test("branch filter applies on submit; empty state names the branch", async () => {
  const branches: (string | null)[] = [];
  server.use(
    http.get("/api/v1/projects/42/runs", ({ request }) => {
      branches.push(new URL(request.url).searchParams.get("branch"));
      return HttpResponse.json([]);
    }),
  );
  renderRuns();
  await screen.findByText(/no runs/i);
  const before = branches.length;
  await userEvent.type(screen.getByLabelText(/branch/i), "release");
  expect(branches.length).toBe(before);
  await userEvent.click(screen.getByRole("button", { name: /apply/i }));
  expect(await screen.findByText(/on release/i)).toBeInTheDocument();
  expect(branches[branches.length - 1]).toBe("release");
});

test("full page enables Next; empty later page keeps Previous reachable", async () => {
  server.use(
    http.get("/api/v1/projects/42/runs", ({ request }) => {
      const offset = Number(new URL(request.url).searchParams.get("offset"));
      return HttpResponse.json(
        offset === 0 ? Array.from({ length: 50 }, (_, i) => run(i + 1)) : [],
      );
    }),
  );
  renderRuns();
  await screen.findByRole("link", { name: /#1\b/ });
  await userEvent.click(screen.getByRole("button", { name: /next/i }));
  await screen.findByText(/no runs/i);
  await userEvent.click(screen.getByRole("button", { name: /previous/i }));
  expect(await screen.findByRole("link", { name: /#1\b/ })).toBeInTheDocument();
});
