import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { Report } from "../../../api/report";
import type { SectionQuery } from "../ReportSection";
import type { Gate } from "../useReportRequest";
import { SUMMARY_REPORT, emptyReport } from "../testFixtures";
import SummarySection, { branchesCsv, bucketsCsv, suggestions, testsCsv } from "./SummarySection";

const READY: Gate = { state: "ready", base: {} as never, key: [] };
const query = (data: Report): SectionQuery => ({ data, error: null, isPending: false, refetch: vi.fn() });

function show(data: Report, handlers = { onClearFilters: vi.fn(), onTry: vi.fn() }) {
  render(
    <MemoryRouter>
      <SummarySection projectId={42} gate={READY} query={query(data)} branch="main" environment="" {...handlers} />
    </MemoryRouter>,
  );
  return handlers;
}

test("tiles carry the value and the delta in words, with better or worse", () => {
  show(SUMMARY_REPORT);
  expect(screen.getByRole("group", { name: "Pass rate 97.8%, up 1.2 points versus the previous 30 days, better" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Failures 2,124, down 14 percent versus the previous 30 days, better" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: /^Average run time 12m 14s, up 5 percent versus the previous 30 days, worse$/ })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: /^Runs 412, up 4 percent versus the previous 30 days$/ })).toBeInTheDocument();  // neutral
  expect(screen.getByText("up 1.2 pts vs previous 30 days")).toBeInTheDocument();
});

test("without a previous period the tiles say so instead of a delta", () => {
  const report = { ...SUMMARY_REPORT, summary: { ...SUMMARY_REPORT.summary!, previous: null } };
  show(report);
  expect(screen.getAllByText("No data in the previous period")).toHaveLength(6);
});

test("the chart is a figure with a caption and a data table; the three tables honour the filters", () => {
  show(SUMMARY_REPORT);
  const figure = screen.getByRole("figure");
  expect(within(figure).getByText(/98,234 executions in 412 runs, pass rate 97\.8%, 96\.6% in the previous period/)).toBeInTheDocument();
  expect(screen.getByText(/show data table/i)).toBeInTheDocument();
  const failing = screen.getByRole("table", { name: /most failing tests/i });
  expect(within(failing).getByRole("link", { name: /checkout › Cart › pays/ })).toHaveAttribute(
    "href", `/projects/42/tests/${"a".repeat(64)}?branch=main`);
  expect(within(screen.getByRole("table", { name: /slowest tests/i })).getByText(/slow one/)).toBeInTheDocument();
  expect(within(screen.getByRole("table", { name: /branches/i })).getByText("main")).toBeInTheDocument();
});

test("no runs: Clear filters and facet suggestions", async () => {
  const { onClearFilters, onTry } = show(emptyReport());
  await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(onClearFilters).toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Try branch release/2.4" }));
  expect(onTry).toHaveBeenCalledWith({ branch: "release/2.4" });
  expect(suggestions(emptyReport(), "main", "")).toEqual([
    { label: "Try branch release/2.4", patch: { branch: "release/2.4" } },
    { label: "Try environment staging", patch: { env: "staging" } },
  ]);
});

test("CSV exports have headers and one row per item", () => {
  expect(bucketsCsv(SUMMARY_REPORT).split("\r\n")).toEqual([
    "date,runs,executions,passed,failed,errored,skipped,pass_rate,previous_date,previous_runs,previous_pass_rate",
    "2026-10-07,14,3301,3200,70,3,28,0.9776,2026-09-07,14,0.97",
    "2026-10-08,14,3301,3200,140,3,28,0.95,2026-09-08,0,",
  ]);
  expect(testsCsv(SUMMARY_REPORT).split("\r\n")[0]).toBe("list,suite,class_name,name,test_key,executions,failures,pass_rate,avg_duration_ms");
  expect(testsCsv(SUMMARY_REPORT).split("\r\n")).toHaveLength(3);
  expect(branchesCsv(SUMMARY_REPORT).split("\r\n")).toEqual(["branch,runs,executions,failures,pass_rate", "main,120,30120,400,0.986"]);
});
