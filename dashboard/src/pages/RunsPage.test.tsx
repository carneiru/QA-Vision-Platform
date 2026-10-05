import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import RunsPage from "./RunsPage";

const run = (id: number) => ({
  id, project_id: 42, ci_provider: "github_actions",
  ci_run_url: "https://ci.example/run/" + id, commit_sha: "abcdef1234567890",
  branch: "main", environment: "ci", agent_version: "0.1.0",
  started_at: "2026-10-01T12:00:00Z", finished_at: "2026-10-01T12:04:00Z",
  duration_ms: 240000, total: 24, passed: 20, failed: 3, skipped: 0, errored: 1,
  created_at: "2026-10-01T12:05:00Z",
});

function Location() {
  const { search } = useLocation();
  return <output data-testid="location">{search}</output>;
}

function renderRuns(url = "/projects/42/runs") {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/projects/:projectId/runs" element={<><RunsPage /><Location /></>} />
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

test("branch filter applies on submit; empty state offers to clear", async () => {
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
  expect(await screen.findByText(/no runs match these filters/i)).toBeInTheDocument();
  expect(branches[branches.length - 1]).toBe("release");
  expect(screen.getByTestId("location")).toHaveTextContent("?branch=release");
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

function captureQueries() {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get("/api/v1/projects/42/runs", ({ request }) => {
      seen.push(new URL(request.url).searchParams);
      return HttpResponse.json([]);
    }),
  );
  return seen;
}

test("filters in the URL drive the first request and prefill the form", async () => {
  const seen = captureQueries();
  renderRuns("/projects/42/runs?status=failing&environment=qa&author=ana");
  await screen.findByText(/no runs match these filters/i);
  const q = seen[seen.length - 1];
  expect(q.get("status")).toBe("failing");
  expect(q.get("environment")).toBe("qa");
  expect(q.get("author")).toBe("ana");
  expect(screen.getByLabelText(/^status/i)).toHaveValue("failing");
  // An active advanced filter keeps "More filters" open
  expect(screen.getByLabelText(/environment/i)).toBeVisible();
  expect(screen.getByLabelText(/author/i)).toHaveValue("ana");
});

test("more filters send commit, PR, CI and a local date range", async () => {
  const seen = captureQueries();
  renderRuns();
  await screen.findByText(/no runs yet/i);
  await userEvent.click(screen.getByText(/more filters/i));
  await userEvent.type(screen.getByLabelText(/commit/i), "abc12");
  await userEvent.type(screen.getByLabelText(/pull request/i), "42");
  await userEvent.selectOptions(screen.getByLabelText(/^ci$/i), "azure_pipelines");
  await userEvent.type(screen.getByLabelText(/^from/i), "2026-10-01");
  await userEvent.type(screen.getByLabelText(/^to/i), "2026-10-03");
  await userEvent.click(screen.getByRole("button", { name: /apply/i }));
  await screen.findByText(/no runs match these filters/i);
  const q = seen[seen.length - 1];
  expect(q.get("commit")).toBe("abc12");
  expect(q.get("pr")).toBe("42");
  expect(q.get("ci_provider")).toBe("azure_pipelines");
  // Whole local days: from midnight on the 1st to midnight after the 3rd
  expect(q.get("since")).toBe(new Date(2026, 9, 1).toISOString());
  expect(q.get("until")).toBe(new Date(2026, 9, 4).toISOString());
  expect(screen.getByTestId("location")).toHaveTextContent("from=2026-10-01");
});

test("clear filters drops every filter and refetches", async () => {
  const seen = captureQueries();
  renderRuns("/projects/42/runs?status=passing&branch=main");
  await userEvent.click(await screen.findByRole("button", { name: /clear filters/i }));
  await screen.findByText(/no runs yet/i);
  const q = seen[seen.length - 1];
  expect([...q.keys()].sort()).toEqual(["limit", "offset"]);
  expect(screen.getByTestId("location")).toBeEmptyDOMElement();
  expect(screen.getByLabelText(/branch/i)).toHaveValue("");
});
