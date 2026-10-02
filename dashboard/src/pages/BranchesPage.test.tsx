import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import BranchesPage from "./BranchesPage";

const branches = [
  { branch: "main", runs: 20, total: 200, passed: 180, failed: 15, errored: 5, skipped: 0,
    pass_rate: 0.9, last_seen: "2026-10-02T10:00:00Z" },
  { branch: "dev", runs: 8, total: 80, passed: 60, failed: 20, errored: 0, skipped: 0,
    pass_rate: 0.75, last_seen: "2026-10-02T09:00:00Z" },
];

function renderBranches() {
  setTokens("acc", "ref");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/branches"]}>
        <Routes>
          <Route path="/projects/:projectId/branches" element={<BranchesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("lists per-branch aggregates", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/branches", () => HttpResponse.json(branches)),
  );
  renderBranches();
  expect(await screen.findByRole("cell", { name: "main" })).toBeInTheDocument();
  expect(screen.getByText("90.0%")).toBeInTheDocument();
  expect(screen.getByText("75.0%")).toBeInTheDocument();
});

test("picking two branches fetches both pass-rate trends", async () => {
  const trendBranches: (string | null)[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/branches", () => HttpResponse.json(branches)),
    http.get("/api/v1/projects/42/analytics/trends", ({ request }) => {
      trendBranches.push(new URL(request.url).searchParams.get("branch"));
      return HttpResponse.json({ tz: "UTC", days: [] });
    }),
  );
  renderBranches();
  await screen.findByRole("cell", { name: "main" });
  await userEvent.selectOptions(screen.getByLabelText(/compare a/i), "main");
  await userEvent.selectOptions(screen.getByLabelText(/compare b/i), "dev");
  await vi.waitFor(() => expect(trendBranches.sort()).toEqual(["dev", "main"]));
});

test("empty window shows an empty state", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/branches", () => HttpResponse.json([])),
  );
  renderBranches();
  expect(await screen.findByText(/no branches/i)).toBeInTheDocument();
});
