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
  renderTrendsIn();
}

function renderTrendsIn() {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
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
  // The page name is the one h1; the org and project live in the breadcrumb
  expect(await screen.findByRole("heading", { level: 1, name: "Trends" })).toBeInTheDocument();
  await userEvent.click((await screen.findAllByText(/show data table/i))[0]);
  expect(screen.getAllByText("2026-09-30").length).toBeGreaterThan(0);
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

function setBucket(b: string) {
  return userEvent.selectOptions(screen.getByLabelText("View"), b);
}

test("charts are not hidden behind role=img: each has a summary and a Show data table disclosure", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", () =>
      HttpResponse.json({ tz: "UTC", days: [day("2026-09-29", 8, 2, 0.8), day("2026-09-30", 9, 1, 0.9)] }),
    ),
  );
  const { container } = renderTrendsIn();
  await screen.findByText("Results per day");
  expect(container.querySelector('[role="img"]')).toBeNull();
  const figures = container.querySelectorAll("figure");
  expect(figures).toHaveLength(2);
  expect(figures[0].querySelector("figcaption")).toHaveTextContent(/17 passed, 3 failed/);
  expect(figures[1].querySelector("figcaption")).toHaveTextContent(/pass rate per day, from 80\.0% to 90\.0%/i);
  const disclosures = container.querySelectorAll("details.chart-data");
  expect(disclosures).toHaveLength(2);
  expect(disclosures[0]).not.toHaveAttribute("open");
  expect(disclosures[0].querySelector("summary")).toHaveTextContent("Show data table");
  expect(disclosures[0].querySelectorAll("tbody tr")).toHaveLength(2);
  expect(screen.queryByRole("button", { name: /view data/i })).not.toBeInTheDocument();
});

test("headings, summaries and the duration tile follow the view (week, month)", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", ({ request }) => {
      const bucket = new URL(request.url).searchParams.get("bucket") ?? "day";
      return HttpResponse.json({ tz: "UTC", bucket, days: [day("2026-09-28", 8, 2, 0.8)] });
    }),
  );
  renderTrendsIn();
  expect(await screen.findByText("Results per day")).toBeInTheDocument();
  expect(screen.getByText("Avg run duration (last day)")).toBeInTheDocument();
  await setBucket("week");
  expect(await screen.findByText("Results per week")).toBeInTheDocument();
  expect(screen.getByText("Pass rate per week")).toBeInTheDocument();
  expect(screen.getByText("Avg run duration (last week)")).toBeInTheDocument();
  expect(screen.getAllByRole("columnheader", { name: "Week of" }).length).toBe(2);
  await setBucket("month");
  expect(await screen.findByText("Results per month")).toBeInTheDocument();
  expect(screen.getAllByRole("columnheader", { name: "Month" }).length).toBe(2);
});

test("the legend toggles series and repeats the bar textures", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", () =>
      HttpResponse.json({ tz: "UTC", days: [day("2026-09-29", 8, 2, 0.8)] }),
    ),
  );
  const { container } = renderTrendsIn();
  const failed = await screen.findByRole("button", { name: "Failed" });
  expect(failed).toHaveAttribute("aria-pressed", "true");
  // The swatch uses the same pattern as the bars, and the pattern is defined once on the page
  expect(failed.querySelector("rect")).toHaveAttribute("fill", "url(#qeos-pat-failed)");
  expect(screen.getByRole("button", { name: "Errored" }).querySelector("rect")).toHaveAttribute("fill", "url(#qeos-pat-errored)");
  for (const id of ["qeos-pat-failed", "qeos-pat-errored", "qeos-pat-skipped"]) {
    expect(container.querySelector(`pattern#${id}`)).not.toBeNull();
  }
  await userEvent.click(failed);
  expect(failed).toHaveAttribute("aria-pressed", "false");
  await userEvent.click(failed);
  expect(failed).toHaveAttribute("aria-pressed", "true");
});
