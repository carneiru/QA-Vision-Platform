import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import RequestedRunsPage from "./RequestedRunsPage";

const P = "/api/v1/projects/42";
const member = (user_id: number, email: string) => ({ id: user_id, organization_id: 1, user_id, email, role: "member",
  status: "active", created_at: "2026-01-01T00:00:00Z", updated_at: null });
const base = { requested_at: "2026-10-07T10:00:00Z", suite_id: null, conclusion: null, github_run_id: null,
  github_run_url: null, stopped_by: null, stopped_at: null, error: null, checked_at: "2026-10-07T10:05:00Z", refreshing: false, skipped_manual: 0 };

function renderPage(items: object[], runs: object[] = []) {
  setAccessToken("acc");
  server.use(
    http.get(P, () => HttpResponse.json({ id: 42, name: "Web", organization_id: 1, my_role: "member" })),
    http.get("/api/v1/organizations/1/members", () => HttpResponse.json([member(7, "ana@example.com"), member(8, "rui@example.com")])),
    http.get(`${P}/run-requests`, () => HttpResponse.json({ total: items.length, items })),
    http.get(`${P}/runs`, () => HttpResponse.json(runs)),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/runs/requested"]}>
        <Routes><Route path="/projects/:projectId/runs/requested" element={<RequestedRunsPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("lists who requested, how many cases, the status, who stopped it, and the links", async () => {
  renderPage([
    { ...base, id: 10, requested_by: 7, selection: [{ case_number: 1, path: "a", name: "A" }, { case_number: 2, path: "a", name: "B" }],
      case_count: 2, status: "completed", conclusion: "success", github_run_id: 501,
      github_run_url: "https://github.com/acme/obt/actions/runs/501" },
    { ...base, id: 9, requested_by: 7, selection: [{ case_number: 1, path: "a", name: "A" }], case_count: 1,
      status: "cancelled", stopped_by: 8, stopped_at: "2026-10-07T10:01:00Z" },
  ], [{ id: 77, ci_run_url: "https://github.com/ACME/obt/actions/runs/501" }]);
  const rows = await screen.findAllByRole("row");
  expect(rows).toHaveLength(3);
  const first = within(rows[1]);
  expect(await first.findByText("ana@example.com")).toBeInTheDocument();
  expect(first.getByText("2")).toBeInTheDocument();
  expect(first.getByText("Passed")).toBeInTheDocument();
  expect(first.getByRole("link", { name: /github/i })).toHaveAttribute("href", "https://github.com/acme/obt/actions/runs/501");
  expect(await first.findByRole("link", { name: "Run #77" })).toHaveAttribute("href", "/projects/42/runs/77");
  expect(within(rows[2]).getByText("rui@example.com")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Runs" })).toHaveAttribute("href", "/projects/42/runs");
});

test("with no requests yet it says so", async () => {
  renderPage([]);
  expect(await screen.findByText("No runs requested from QEOS yet.")).toBeInTheDocument();
});

test("shows why a request is stale or was cancelled, and looks results up among GitHub Actions runs only", async () => {
  let query = "";
  renderPage([
    { ...base, id: 12, requested_by: 7, selection: [], case_count: 1, status: "running", refreshing: true,
      github_run_url: "https://github.com/acme/obt/actions/runs/9", error: "token invalid or expired" },
    { ...base, id: 11, requested_by: 7, selection: [], case_count: 1, status: "cancelled", error: "The run is no longer on GitHub" },
  ]);
  server.use(http.get(`${P}/runs`, ({ request }) => { query = new URL(request.url).search; return HttpResponse.json([]); }));
  expect(await screen.findByText("GitHub: token invalid or expired")).toBeInTheDocument();
  expect(screen.getByText("Cancelled: The run is no longer on GitHub")).toBeInTheDocument();
  await vi.waitFor(() => expect(query).toContain("ci_provider=github_actions"));
});
