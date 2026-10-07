import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import TestsPage from "./TestsPage";
import TrendsPage from "./TrendsPage";
import FlakyPage from "./FlakyPage";
import HistoryPage from "./HistoryPage";
import BranchesPage from "./BranchesPage";
import RunsPage from "./RunsPage";
import RequestedRunsPage from "./RequestedRunsPage";

const A = "/api/v1/projects/42/analytics";

function Where() {
  const { pathname, search } = useLocation();
  return <output data-testid="where">{pathname + search}</output>;
}
const where = () => screen.getByTestId("where").textContent;

function renderAt(url: string) {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/projects/:projectId/tests" element={<><TestsPage /><Where /></>} />
          <Route path="/projects/:projectId/tests/:testKey" element={<><HistoryPage /><Where /></>} />
          <Route path="/projects/:projectId/trends" element={<><TrendsPage /><Where /></>} />
          <Route path="/projects/:projectId/flaky" element={<><FlakyPage /><Where /></>} />
          <Route path="/projects/:projectId/branches" element={<><BranchesPage /><Where /></>} />
          <Route path="/projects/:projectId/runs" element={<><RunsPage /><Where /></>} />
          <Route path="/projects/:projectId/runs/requested" element={<><RequestedRunsPage /><Where /></>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const testRow = (i: number) => ({
  test_key: `k${i}`, suite: "s", class_name: "C", name: `t${i}`, runs: 1, passed: 1, failed: 0, errored: 0,
  skipped: 0, pass_rate: 1, avg_duration_ms: 1, last_status: "passed", last_seen: "2026-09-30T10:00:00Z",
});
const run = (id: number) => ({
  id, project_id: 42, ci_provider: "other", ci_run_url: null, commit_sha: null, branch: null, environment: null,
  started_at: "2026-10-01T12:00:00Z", duration_ms: 1, passed: 1, failed: 0, errored: 0, skipped: 0,
});

/** Records the query string of every call to a handler, answering with `body`. */
function spy(path: string, body: unknown) {
  const seen: URLSearchParams[] = [];
  server.use(http.get(path, ({ request }) => {
    seen.push(new URL(request.url).searchParams);
    return HttpResponse.json(body as object);
  }));
  return seen;
}

describe("Tests", () => {
  test("filters, sort and page are read from the URL", async () => {
    const seen = spy(`${A}/tests`, Array.from({ length: 51 }, (_, i) => testRow(i)));
    renderAt("/projects/42/tests?days=7&sort=name&search=login&offset=50");
    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    const last = seen.at(-1)!;
    expect([last.get("days"), last.get("sort"), last.get("search"), last.get("offset")]).toEqual(["7", "name", "login", "50"]);
    expect(screen.getByLabelText("Days")).toHaveValue("7");
  });

  test("changing a filter updates the URL, resets the page, and leaves out defaults", async () => {
    spy(`${A}/tests`, Array.from({ length: 51 }, (_, i) => testRow(i)));
    renderAt("/projects/42/tests?offset=50");
    await screen.findByText("t0");
    await userEvent.selectOptions(screen.getByLabelText("Sort"), "duration");
    expect(where()).toBe("/projects/42/tests?sort=duration");
    await userEvent.selectOptions(screen.getByLabelText("Sort"), "failures");
    expect(where()).toBe("/projects/42/tests");
  });

  test("Next is disabled on an exact multiple of the page size", async () => {
    spy(`${A}/tests`, Array.from({ length: 50 }, (_, i) => testRow(i)));
    renderAt("/projects/42/tests");
    await screen.findByText("t0");
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  test("Next pages through the URL", async () => {
    spy(`${A}/tests`, Array.from({ length: 51 }, (_, i) => testRow(i)));
    renderAt("/projects/42/tests?days=7");
    await screen.findByText("t0");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(where()).toBe("/projects/42/tests?days=7&offset=50");
  });
});

describe("Trends", () => {
  const empty = { days: [] };
  test("reads days, view, branch and environment from the URL", async () => {
    const seen = spy(`${A}/trends`, empty);
    renderAt("/projects/42/trends?days=90&bucket=week&branch=main&environment=ci");
    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    const last = seen.at(-1)!;
    expect([last.get("days"), last.get("bucket"), last.get("branch"), last.get("environment")]).toEqual(["90", "week", "main", "ci"]);
  });
  test("a change updates the URL; Apply writes the text filters", async () => {
    spy(`${A}/trends`, empty);
    renderAt("/projects/42/trends");
    await userEvent.selectOptions(screen.getByLabelText("Days"), "7");
    expect(where()).toBe("/projects/42/trends?days=7");
    await userEvent.type(screen.getByLabelText("Branch"), "dev");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(where()).toBe("/projects/42/trends?days=7&branch=dev");
  });
});

describe("Flaky", () => {
  test("reads the window, thresholds, branch and quarantine toggle from the URL", async () => {
    const seen = spy(`${A}/flaky`, []);
    renderAt("/projects/42/flaky?window=30&min_runs=8&min_flip=0.5&branch=main&muted=1");
    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    const last = seen.at(-1)!;
    expect([last.get("window_days"), last.get("min_runs"), last.get("min_flip_rate"), last.get("branch"), last.get("include_muted")])
      .toEqual(["30", "8", "0.5", "main", "true"]);
  });
  test("changes update the URL", async () => {
    spy(`${A}/flaky`, []);
    renderAt("/projects/42/flaky");
    await userEvent.selectOptions(screen.getByLabelText("Window (days)"), "30");
    expect(where()).toBe("/projects/42/flaky?window=30");
    await userEvent.click(screen.getByLabelText("Show quarantined"));
    expect(where()).toBe("/projects/42/flaky?window=30&muted=1");
  });
});

describe("History", () => {
  const history = { test_key: "k1", name: "n", suite: "s", class_name: "C", summary: { runs: 0, pass_rate: null, avg_duration_ms: null }, executions: [] };
  test("reads days and branch from the URL", async () => {
    const seen = spy(`${A}/tests/k1/history`, history);
    renderAt("/projects/42/tests/k1?days=90&branch=dev");
    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    expect([seen.at(-1)!.get("days"), seen.at(-1)!.get("branch")]).toEqual(["90", "dev"]);
  });
  test("changes update the URL", async () => {
    spy(`${A}/tests/k1/history`, history);
    renderAt("/projects/42/tests/k1");
    await screen.findByRole("heading", { name: "n" });
    await userEvent.selectOptions(screen.getByLabelText("Days"), "7");
    expect(where()).toBe("/projects/42/tests/k1?days=7");
    await userEvent.type(screen.getByLabelText("Branch"), "x");
    expect(where()).toBe("/projects/42/tests/k1?days=7&branch=x");
  });
});

describe("Branches", () => {
  const branches = [
    { branch: "main", runs: 1, passed: 1, failed: 0, errored: 0, skipped: 0, pass_rate: 1, last_seen: "2026-09-30T10:00:00Z" },
    { branch: "dev", runs: 1, passed: 1, failed: 0, errored: 0, skipped: 0, pass_rate: 1, last_seen: "2026-09-30T10:00:00Z" },
  ];
  test("reads days and the compared branches from the URL", async () => {
    spy(`${A}/branches`, branches);
    const seen = spy(`${A}/trends`, { days: [] });
    renderAt("/projects/42/branches?days=7&a=main&b=dev");
    await waitFor(() => expect(seen.length).toBeGreaterThanOrEqual(2));
    expect(seen.map((s) => s.get("branch")).sort()).toEqual(["dev", "main"]);
    expect(screen.getByLabelText("Compare A")).toHaveValue("main");
  });
  test("changes update the URL", async () => {
    spy(`${A}/branches`, branches);
    renderAt("/projects/42/branches");
    await screen.findAllByRole("option", { name: "main" });
    await userEvent.selectOptions(screen.getByLabelText("Days"), "90");
    expect(where()).toBe("/projects/42/branches?days=90");
  });
});

describe("paged lists", () => {
  test("Runs: offset comes from and goes to the URL", async () => {
    const seen = spy("/api/v1/projects/42/runs", Array.from({ length: 50 }, (_, i) => run(i + 1)));
    renderAt("/projects/42/runs?offset=100&branch=main");
    await waitFor(() => expect(seen.at(-1)?.get("offset")).toBe("100"));
    await screen.findByText("#1");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(where()).toBe("/projects/42/runs?offset=150&branch=main");
  });
  test("Requested runs: offset comes from and goes to the URL", async () => {
    const seen = spy("/api/v1/projects/42/run-requests", { total: 200, items: [] });
    server.use(http.get("/api/v1/projects/42", () => HttpResponse.json({ id: 42, organization_id: 1, name: "W", my_role: "member" })));
    renderAt("/projects/42/runs/requested?offset=50");
    await waitFor(() => expect(seen.at(-1)?.get("offset")).toBe("50"));
  });
});
