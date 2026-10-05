import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import ReportPage from "./ReportPage";

const A = "/api/v1/projects/42/analytics";

function week(date: string, runs: number, total: number, passed: number, failed: number, skipped = 0) {
  return { date, runs, total, passed, failed, errored: 0, skipped, pass_rate: passed / (total - skipped),
           avg_run_duration_ms: 60000, max_run_duration_ms: 90000 };
}

function test_(name: string, failed: number, avg: number) {
  return { test_key: name, suite: "checkout", class_name: "Cart", name, runs: 10, passed: 10 - failed, failed,
           errored: 0, skipped: 0, pass_rate: (10 - failed) / 10, avg_duration_ms: avg, last_status: failed ? "failed" : "passed",
           last_seen: "2026-10-05T10:00:00Z" };
}

let seen: URL[] = [];

function serve() {
  seen = [];
  server.use(
    http.get("/api/v1/projects/42", () => HttpResponse.json({ id: 42, name: "Web Shop", organization_id: 1, my_role: "viewer" })),
    http.get(`${A}/trends`, ({ request }) => {
      seen.push(new URL(request.url));
      return HttpResponse.json({ tz: "UTC", bucket: "week", days: [
        week("2026-09-22", 10, 1000, 950, 40, 10), week("2026-09-29", 12, 1200, 1100, 90, 10),
      ] });
    }),
    http.get(`${A}/tests`, ({ request }) => {
      const sort = new URL(request.url).searchParams.get("sort");
      return HttpResponse.json(sort === "duration"
        ? [test_("slow one", 0, 92000), test_("medium", 0, 30000)]
        : [test_("pays", 4, 1200), test_("ships", 1, 800), test_("never fails", 0, 100)]);
    }),
    http.get(`${A}/flaky`, () => HttpResponse.json([{ test_key: "f", suite: "checkout", class_name: "Cart", name: "coupon",
      reason: "flips", commits: [], flips: 4, flip_rate: 0.4, runs: 10, last_status: "passed", last_seen: "2026-10-05T10:00:00Z" }])),
    http.get(`${A}/branches`, () => HttpResponse.json([{ branch: "main", runs: 20, total: 2000, passed: 1900, failed: 100,
      errored: 0, skipped: 0, pass_rate: 0.95, last_seen: "2026-10-05T10:00:00Z" }])),
  );
}

function renderPage() {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/report"]}>
        <Routes>
          <Route path="/projects/:projectId/report" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("the summary adds up the period: runs, executions, pass rate without skipped, failures", async () => {
  serve();
  renderPage();
  expect(await screen.findByRole("heading", { name: /web shop: quality report/i })).toBeInTheDocument();
  const summary = screen.getByRole("region", { name: /summary/i });
  expect(within(summary).getByText("22")).toBeInTheDocument();                // runs
  expect(within(summary).getByText("2,200")).toBeInTheDocument();             // executions
  expect(within(summary).getByText("94.0%")).toBeInTheDocument();             // 2050 / (2200 - 20)
  expect(within(summary).getByText("130")).toBeInTheDocument();               // failed + errored
});

test("weekly table, top failing (only tests that failed), slowest, flaky and branches", async () => {
  serve();
  renderPage();
  const weekly = await screen.findByRole("table", { name: /pass rate by week/i });
  expect(within(weekly).getAllByRole("row")).toHaveLength(3);
  const failing = screen.getByRole("table", { name: /most failing tests/i });
  expect(within(failing).getByText(/pays/)).toBeInTheDocument();
  expect(within(failing).queryByText(/never fails/)).not.toBeInTheDocument();
  expect(within(screen.getByRole("table", { name: /slowest tests/i })).getByText(/slow one/)).toBeInTheDocument();
  expect(within(screen.getByRole("table", { name: /flaky tests/i })).getByText(/coupon/)).toBeInTheDocument();
  expect(within(screen.getByRole("table", { name: /branches/i })).getByText("main")).toBeInTheDocument();
});

test("changing the period asks for that period", async () => {
  serve();
  renderPage();
  await screen.findByRole("table", { name: /pass rate by week/i });
  await userEvent.selectOptions(screen.getByLabelText(/period/i), "90");
  await vi.waitFor(() => expect(seen.some((u) => u.searchParams.get("days") === "90")).toBe(true));
  expect(seen[0].searchParams.get("bucket")).toBe("week");
});

test("save as PDF prints the page; CSV downloads the tests behind the report", async () => {
  serve();
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  Object.assign(URL, { createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  renderPage();
  await screen.findByRole("table", { name: /pass rate by week/i });
  await userEvent.click(screen.getByRole("button", { name: /save as pdf/i }));
  expect(print).toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: /download csv/i }));
  await vi.waitFor(() => expect(click).toHaveBeenCalled());
  print.mockRestore();
  click.mockRestore();
});
