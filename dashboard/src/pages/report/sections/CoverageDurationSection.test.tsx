import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { Report } from "../../../api/report";
import { parseReportFilters } from "../useReportFilters";
import type { Gate } from "../useReportRequest";
import { AREAS_FIXTURE, TESTS_REPORT } from "../testFixtures";
import AreaSection from "./AreaSection";
import CoverageDurationSection, { coverageGroups, durationCsv, neverRunCsv } from "./CoverageDurationSection";

const READY: Gate = { state: "ready", base: {} as never, key: [] };
const filters = (q = "") => parseReportFilters(new URLSearchParams(q), "2026-10-08").filters;
const q = { data: TESTS_REPORT, error: null, isPending: false, refetch: vi.fn() };
const areas = { data: AREAS_FIXTURE, error: null, refetch: vi.fn() };

function show(report: Report = TESTS_REPORT, f = filters()) {
  return render(
    <MemoryRouter>
      <CoverageDurationSection projectId={42} gate={READY} testsQuery={{ ...q, data: report }} durationQuery={{ ...q, data: report }}
        caseAreas={areas} filters={f} onResetFilters={vi.fn()} />
    </MemoryRouter>,
  );
}

test("coverage tiles and the never-run table under the current filters", () => {
  show();
  expect(screen.getByRole("group", { name: "Active cases 4" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Linked (automated) 3" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Manual 1" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Automated, not run in this period 1" })).toBeInTheDocument();
  const table = screen.getByRole("table", { name: /automated, not run in this period/i });
  expect(within(table).getByRole("link", { name: "TC-3" })).toHaveAttribute("href", "/projects/42/cases/3");
  expect(screen.getByText(/under the current filters/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /1 test without a case/i })).toHaveAttribute("href", "/projects/42/tests");
});

test("the duration chart names its basis", () => {
  const first = show();
  expect(screen.getByRole("heading", { name: "Run time (wall clock)" })).toBeInTheDocument();
  first.unmount();
  show({ ...TESTS_REPORT, duration: { ...TESTS_REPORT.duration!, basis: "test_time" } }, filters("area=feature:Payments"));
  expect(screen.getByRole("heading", { name: "Time in selected tests (summed)" })).toBeInTheDocument();
});

test("slowest areas by total test time", () => {
  show();
  const rows = within(screen.getByRole("table", { name: /slowest areas/i })).getAllByRole("row");
  expect(rows[1]).toHaveTextContent("Payments");                       // 400,000 ms beats Booking's 90,000
});

test("CSVs and coverage groups", () => {
  expect(neverRunCsv(AREAS_FIXTURE.cases.slice(2, 3)).split("\r\n")).toEqual(["case,title,folder,feature", "TC-3,Refund,features/payments,Payments"]);
  expect(durationCsv(TESTS_REPORT).split("\r\n")[0]).toBe("date,runs,avg_ms,p50_ms,p90_ms,max_ms");
  expect(durationCsv({ ...TESTS_REPORT, duration: undefined })).toBe("date,runs,avg_ms,p50_ms,p90_ms,max_ms");
  expect(coverageGroups(AREAS_FIXTURE, "feature", 1)).toEqual([
    { label: "Payments", linked: 2, manual: 0 }, { label: "Booking", linked: 1, manual: 0 }, { label: "No feature", linked: 0, manual: 1 },
  ]);
});

test("a cut test list hides the never-run list and the unlinked count, and says why", () => {
  show({ ...TESTS_REPORT, tests: { ...TESTS_REPORT.tests!, truncated: true } });
  expect(screen.queryByRole("table", { name: /automated, not run in this period/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /without a case/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("group", { name: /^Automated, not run in this period 1/ })).not.toBeInTheDocument();
  expect(screen.getByText(/cut at 50,000 tests/i)).toBeInTheDocument();
});

test("a response without tests or duration renders what it has", () => {
  show({ ...TESTS_REPORT, tests: undefined, duration: undefined });
  expect(screen.getByRole("group", { name: "Active cases 4" })).toBeInTheDocument();
  expect(screen.getByText(/per-test numbers are not in this response/i)).toBeInTheDocument();
  expect(screen.getByText(/run times are not in this response/i)).toBeInTheDocument();
});

test("sections 3 and 5 each have their own grouping control, with distinct ids", () => {
  render(
    <MemoryRouter>
      <AreaSection projectId={42} gate={READY} caseAreas={areas} onResetFilters={vi.fn()} query={q} />
      <CoverageDurationSection projectId={42} gate={READY} testsQuery={q} durationQuery={q} caseAreas={areas} filters={filters()} onResetFilters={vi.fn()} />
    </MemoryRouter>,
  );
  const groups = screen.getAllByRole("group", { name: "Group by" });
  expect(groups).toHaveLength(2);
  const ids = groups.map((g) => g.getAttribute("aria-labelledby"));
  expect(new Set(ids).size).toBe(2);
  ids.forEach((id) => expect(document.querySelectorAll(`[id="${id}"]`)).toHaveLength(1));
});

test("each chart has a legend that tells the series apart and can hide one", async () => {
  show();
  const coverage = screen.getByRole("list", { name: /coverage chart/i });
  expect(within(coverage).getByRole("button", { name: "Linked (automated)" })).toHaveAttribute("aria-pressed", "true");
  expect(within(coverage).getByRole("button", { name: "Manual (striped)" })).toBeInTheDocument();
  const duration = screen.getByRole("list", { name: /duration chart/i });
  expect(within(duration).getByRole("button", { name: "Average" })).toBeInTheDocument();
  await userEvent.click(within(duration).getByRole("button", { name: "p90 (dashed)" }));
  expect(within(duration).getByRole("button", { name: "p90 (dashed)" })).toHaveAttribute("aria-pressed", "false");
});

test("a previous period without an average is not compared in the caption", () => {
  show({ ...TESTS_REPORT, duration: { ...TESTS_REPORT.duration!, previous: { runs: 0, avg_ms: null, p50_ms: null, p90_ms: null } } });
  expect(screen.getByText(/the longest is/)).not.toHaveTextContent(/against/);
  expect(screen.getByText(/the longest is/)).toHaveTextContent(/the longest is .* at /);
});

test("Retry asks again only for the request that failed", async () => {
  const tests = { ...q, data: TESTS_REPORT, refetch: vi.fn() };
  const duration = { ...q, data: undefined, error: new Error("boom"), refetch: vi.fn() };
  render(
    <MemoryRouter>
      <CoverageDurationSection projectId={42} gate={READY} testsQuery={tests} durationQuery={duration}
        caseAreas={areas} filters={filters()} onResetFilters={vi.fn()} />
    </MemoryRouter>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(duration.refetch).toHaveBeenCalledTimes(1);
  expect(tests.refetch).not.toHaveBeenCalled();
});
