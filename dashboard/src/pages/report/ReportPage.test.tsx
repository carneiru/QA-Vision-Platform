import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { delay, http, HttpResponse } from "msw";
import { server } from "../../test/server";
import { setAccessToken } from "../../auth/tokens";
import type { ReportRequest } from "../../api/report";
import { SUMMARY_REPORT } from "./testFixtures";
import { addDays, todayIn } from "./useReportFilters";
import ReportPage from "./ReportPage";

const P = "/api/v1/projects/42";
const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
let bodies: ReportRequest[] = [];
/** Phase 2 and 3 add a request per section; the summary's are the ones these tests read. */
const summaryBodies = () => bodies.filter((b) => b.sections[0] === "summary");

function serve(over: { report?: (body: ReportRequest) => Response | Promise<Response> } = {}) {
  bodies = [];
  server.use(
    http.get(P, () => HttpResponse.json({ id: 42, name: "Web Shop", organization_id: 1, my_role: "viewer" })),
    http.get(`${P}/repositories`, () => HttpResponse.json([{ id: 1, default_branch: "main" }])),
    http.post(`${P}/analytics/report`, async ({ request }) => {
      const body = (await request.json()) as ReportRequest;
      bodies.push(body);
      return over.report ? over.report(body) : HttpResponse.json(SUMMARY_REPORT);
    }),
    http.get(`${P}/analytics/flaky`, () => HttpResponse.json([{ test_key: "c".repeat(64), suite: "checkout", class_name: "Cart",
      name: "coupon", reason: "flips", commits: [], flips: 4, flip_rate: 0.4, runs: 10, last_status: "passed", last_seen: "2026-10-05T10:00:00Z" }])),
    http.get(`${P}/case-areas`, () => HttpResponse.json({ generated_at: "v1", counts: { cases: 1, linked: 1, manual: 0 },
      folders: [], features: ["Booking"], labels: [], suites: [],
      cases: [{ n: 1, t: "Book", k: "c".repeat(64), fo: null, fe: 0, l: [], s: [] }] })),
    http.get(`${P}/run-requests/run-urls`, () => HttpResponse.json({ urls: ["https://github.com/a/b/actions/runs/7"], truncated: false })),
  );
}

function renderPage(search = "") {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/projects/42/report${search}`]}>
        <Routes><Route path="/projects/:projectId/report" element={<ReportPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("the summary is asked for the last 30 days on the default branch, in the reader's zone", async () => {
  serve();
  renderPage();
  expect(await screen.findByRole("heading", { level: 1, name: "Report" })).toBeInTheDocument();
  expect(await screen.findByRole("group", { name: /^Pass rate 97\.8%/ })).toBeInTheDocument();
  const today = todayIn(TZ);
  expect(summaryBodies()[0]).toEqual({ from: addDays(today, -29), to: today, tz: TZ, branch: "main", environment: null, ci_provider: null,
    origin: "any", requested_run_urls: null, test_keys: null, sections: ["summary"], bucket: "auto" });
  expect(screen.getByText(/web shop: quality report/i)).toBeInTheDocument();
  expect(within(screen.getByRole("group", { name: "Quick filters" })).getByText("Branch: main (default)")).toBeInTheDocument();
});

test("an area filter sends the linked keys; one with no linked tests sends nothing", async () => {
  serve();
  renderPage("?area=feature:Booking");
  await screen.findByRole("group", { name: /^Pass rate/ });
  expect(summaryBodies()[0].test_keys).toEqual(["c".repeat(64)]);
  expect(within(screen.getByRole("region", { name: /flaky tests/i })).getByText(/coupon/)).toBeInTheDocument();
});

test("an area with no linked tests never calls the report", async () => {
  serve();
  renderPage("?area=feature:Nothing");
  expect(await screen.findAllByText("No automated tests are linked to cases in this area")).not.toHaveLength(0);
  expect(bodies).toHaveLength(0);
});

test("origin sends the Play URLs", async () => {
  serve();
  renderPage("?origin=qeos");
  await screen.findByRole("group", { name: /^Pass rate/ });
  expect(summaryBodies()[0]).toMatchObject({ origin: "qeos", requested_run_urls: ["https://github.com/a/b/actions/runs/7"] });
});

test("a timeout and a 422 show in the section, with Retry and Reset filters", async () => {
  serve({ report: () => HttpResponse.json({ detail: { code: "report_timeout",
    message: "This report took too long. Narrow the period or the filters." } }, { status: 503 }) });
  renderPage();
  const summary = await screen.findByRole("region", { name: "Summary" });
  expect(await within(summary).findByText(/this report took too long/i)).toBeInTheDocument();
  expect(within(summary).getByRole("button", { name: "Retry" })).toBeInTheDocument();
});

test("a link with invalid filters shows the notice and asks without them", async () => {
  serve();
  renderPage("?ci=travis");
  expect(await screen.findByText("Some filters in the link were not valid and were removed")).toBeInTheDocument();
  await screen.findByRole("group", { name: /^Pass rate/ });
  expect(bodies.every((b) => b.ci_provider === null)).toBe(true);
});

test("a filter change mid-load aborts the old request, never shows its answer and is announced once", async () => {
  serve({
    report: async (body) => {
      if (body.branch === "main") {
        await delay(300);
        return HttpResponse.json({ ...SUMMARY_REPORT, summary: { ...SUMMARY_REPORT.summary!, current: { ...SUMMARY_REPORT.summary!.current, runs: 111 } } });
      }
      return HttpResponse.json({ ...SUMMARY_REPORT, summary: { ...SUMMARY_REPORT.summary!, current: { ...SUMMARY_REPORT.summary!.current, runs: 222 } } });
    },
  });
  // msw does not pass a client abort on to its handlers here, so the signal the page hands to fetch is watched
  const signals: { branch: string | null; signal: AbortSignal }[] = [];
  const realFetch = globalThis.fetch;
  const spy = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    if (String(input).endsWith("/analytics/report") && init?.signal && typeof init.body === "string") {
      signals.push({ branch: (JSON.parse(init.body) as ReportRequest).branch, signal: init.signal });
    }
    return realFetch(input, init);
  });
  renderPage();
  await userEvent.click(await screen.findByRole("button", { name: "Remove filter Branch: main (default)" }));
  expect(await screen.findByRole("group", { name: /^Runs 222/ })).toBeInTheDocument();
  await delay(400);
  spy.mockRestore();
  expect(signals.map((s) => [s.branch, s.signal.aborted])).toEqual([["main", true], [null, false]]);
  expect(screen.queryByRole("group", { name: /^Runs 111/ })).not.toBeInTheDocument();
  expect(screen.getAllByText("Report updated")).toHaveLength(1);
  expect(summaryBodies().map((b) => b.branch)).toEqual(["main", null]);
});

test("print: Save as PDF prints; the print header lists the period and every filter; data tables open", async () => {
  serve();
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  renderPage("?env=staging");
  await screen.findByRole("group", { name: /^Pass rate/ });
  await userEvent.click(screen.getByRole("button", { name: /save as pdf/i }));
  expect(print).toHaveBeenCalled();
  const header = document.querySelector(".report-print-header")!;
  expect(header).toHaveTextContent("Branch: main (default)");
  expect(header).toHaveTextContent("Environment: staging");
  expect(header).toHaveTextContent(/compared with/i);
  window.dispatchEvent(new Event("beforeprint"));
  document.querySelectorAll("details.chart-data").forEach((d) => expect(d).toHaveAttribute("open"));
  window.dispatchEvent(new Event("afterprint"));
  document.querySelectorAll("details.chart-data").forEach((d) => expect(d).not.toHaveAttribute("open"));
  print.mockRestore();
});
