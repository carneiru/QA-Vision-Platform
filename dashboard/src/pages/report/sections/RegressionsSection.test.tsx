import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { Gate } from "../useReportRequest";
import { REGRESSIONS_REPORT } from "../testFixtures";
import RegressionsSection, { fixedCsv, formatSpan, longestCsv, newlyCsv } from "./RegressionsSection";

const READY: Gate = { state: "ready", base: {} as never, key: [] };

function show() {
  render(
    <MemoryRouter>
      <RegressionsSection projectId={42} gate={READY} branch="main" onResetFilters={vi.fn()}
        query={{ data: REGRESSIONS_REPORT, error: null, isPending: false, refetch: vi.fn() }} />
    </MemoryRouter>,
  );
}

test("tiles: newly failing, fixed, still failing, median time to fix with the bounded count", () => {
  show();
  expect(screen.getByRole("group", { name: "Newly failing 9" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Fixed 5" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Still failing 12" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Median time to fix 1 day (2 at least)" })).toBeInTheDocument();
});

test("the instability chart is labelled flips and explains it differs from the Flaky page", () => {
  show();
  expect(screen.getByRole("heading", { name: /instability \(flips\)/i })).toBeInTheDocument();
  expect(screen.getByText(/same-commit rule/i)).toBeInTheDocument();
  expect(within(screen.getByRole("figure")).getByText(/14 flaky tests of 990/i)).toBeInTheDocument();
});

test("three tables link to the test history on its branch and to the run; bounded starts say at least", () => {
  show();
  const newly = screen.getByRole("table", { name: /newly failing/i });
  expect(within(newly).getByRole("link", { name: /checkout › Cart › pays/ })).toHaveAttribute(
    "href", `/projects/42/tests/${"pays".padEnd(64, "0")}?branch=main`);
  expect(within(newly).getByRole("link", { name: /run #9301/ })).toHaveAttribute("href", "/projects/42/runs/9301");
  expect(within(screen.getByRole("table", { name: /^fixed/i })).getByText(/at least since/i)).toBeInTheDocument();
  expect(within(screen.getByRole("table", { name: /longest failing/i })).getByText(/at least since/i)).toBeInTheDocument();
  expect(screen.getByText(/and 8 more/i)).toBeInTheDocument();       // newly failing: 9 total, 1 shown
});

test("a report without the regressions section renders nothing in the body", () => {
  render(
    <MemoryRouter>
      <RegressionsSection projectId={42} gate={READY} branch={null} onResetFilters={vi.fn()}
        query={{ data: { ...REGRESSIONS_REPORT, regressions: undefined }, error: null, isPending: false, refetch: vi.fn() }} />
    </MemoryRouter>,
  );
  expect(screen.getByRole("region", { name: "Regressions and stability" })).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

test("spans and CSVs", () => {
  expect(formatSpan(null)).toBe("—");
  expect(formatSpan(90 * 60_000)).toBe("1.5 h");
  expect(formatSpan(86_400_000)).toBe("1 day");
  expect(formatSpan(432_000_000)).toBe("5 days");
  expect(newlyCsv(REGRESSIONS_REPORT).split("\r\n")[0]).toBe("suite,class_name,name,test_key,branch,failing_since,last_passed_at,failures,headline");
  expect(fixedCsv(REGRESSIONS_REPORT).split("\r\n")[0]).toBe("suite,class_name,name,test_key,branch,fixed_at,failing_since,failing_since_bounded,time_to_fix_ms");
  expect(longestCsv(REGRESSIONS_REPORT).split("\r\n")).toHaveLength(2);
});
