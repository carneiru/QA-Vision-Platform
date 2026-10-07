import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { delay, http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import TrendsPage from "./TrendsPage";

const day = (date: string, passed: number, failed: number, pass_rate: number | null) => ({
  date, runs: 2, total: passed + failed, passed, failed,
  errored: 0, skipped: 0, pass_rate, avg_run_duration_ms: 1200, max_run_duration_ms: 3000,
});

function renderTrends() {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/trends"]}>
        <Routes>
          <Route path="/projects/:projectId/trends" element={<TrendsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders stat tiles and the data table with null pass_rate as em dash", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", () =>
      HttpResponse.json({ tz: "UTC", days: [day("2026-09-29", 8, 2, 0.8), day("2026-09-30", 0, 0, null)] }),
    ),
  );
  renderTrends();
  await userEvent.click(await screen.findByRole("button", { name: /view data/i }));
  expect(screen.getByText("2026-09-30")).toBeInTheDocument();
  expect(screen.getAllByText("—").length).toBeGreaterThan(0); // null pass_rate rendered as em dash
  expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
});

test("empty window shows an empty state naming the filters", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", () =>
      HttpResponse.json({ tz: "UTC", days: [] }),
    ),
  );
  renderTrends();
  expect(await screen.findByText(/no runs in the last 30 days/i)).toBeInTheDocument();
});

test("branch input fetches only on Apply, not per keystroke", async () => {
  const branches: (string | null)[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", ({ request }) => {
      branches.push(new URL(request.url).searchParams.get("branch"));
      return HttpResponse.json({ tz: "UTC", days: [] });
    }),
  );
  renderTrends();
  await screen.findByText(/no runs/i);
  const fetchesBeforeTyping = branches.length;
  await userEvent.type(screen.getByLabelText(/branch/i), "main");
  expect(branches.length).toBe(fetchesBeforeTyping); // nothing while typing
  await userEvent.click(screen.getByRole("button", { name: /apply/i }));
  await screen.findByText(/on main/i);
  expect(branches[branches.length - 1]).toBe("main");
});

test("changing days refetches with the new value", async () => {
  const seen: string[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", ({ request }) => {
      seen.push(new URL(request.url).searchParams.get("days")!);
      return HttpResponse.json({ tz: "UTC", days: [] });
    }),
  );
  renderTrends();
  await screen.findByText(/no runs/i);
  await userEvent.selectOptions(screen.getByLabelText(/days/i), "90");
  await screen.findByText(/no runs in the last 90 days/i);
  expect(seen).toContain("90");
});


test("bucket select refetches weekly", async () => {
  const buckets: (string | null)[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", ({ request }) => {
      buckets.push(new URL(request.url).searchParams.get("bucket"));
      return HttpResponse.json({ tz: "UTC", bucket: "week", days: [] });
    }),
  );
  renderTrends();
  await screen.findByText(/no runs/i);
  await userEvent.selectOptions(screen.getByLabelText(/view/i), "week");
  await vi.waitFor(() => expect(buckets[buckets.length - 1]).toBe("week"));
});

test("while trends load, placeholders reserve the tiles and both charts", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", async () => {
      await delay(100);
      return HttpResponse.json({ tz: "UTC", days: [day("2026-09-29", 8, 2, 0.8)] });
    }),
  );
  renderTrends();
  const status = screen.getByRole("status", { name: /loading trends/i });
  expect(status.querySelectorAll(".skeleton-card").length).toBeGreaterThanOrEqual(5); // three tiles, two charts
  expect(await screen.findByText("Results per day")).toBeInTheDocument();
  expect(screen.queryByRole("status", { name: /loading trends/i })).not.toBeInTheDocument();
});
