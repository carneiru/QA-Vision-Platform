import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { CaseAreas } from "../../../api/cases";
import type { Report } from "../../../api/report";
import type { Gate } from "../useReportRequest";
import { AREAS_FIXTURE, SUMMARY_REPORT, TESTS_REPORT } from "../testFixtures";
import AreaSection, { areasCsv } from "./AreaSection";
import { decodeTests, groupByArea } from "../../../lib/reportScope";

const READY: Gate = { state: "ready", base: {} as never, key: [] };

function Search() {
  return <output data-testid="search">{useLocation().search}</output>;
}

interface CaseAreasQuery { data?: CaseAreas; error: unknown; refetch: () => unknown }

function show(
  search = "",
  caseAreas: CaseAreasQuery = { data: AREAS_FIXTURE, error: null, refetch: vi.fn() },
  data: Report = TESTS_REPORT,
) {
  render(
    <MemoryRouter initialEntries={[`/projects/42/report${search}`]}>
      <Routes><Route path="/projects/:projectId/report" element={<>
        <AreaSection projectId={42} gate={READY} caseAreas={caseAreas} onResetFilters={vi.fn()}
          query={{ data, error: null, isPending: false, refetch: vi.fn() }} />
        <Search />
      </>} /></Routes>
    </MemoryRouter>,
  );
}

test("by feature, worst first, with links to the Cases list and the No case row", () => {
  show();
  const table = screen.getByRole("table", { name: /by area/i });
  const rows = within(table).getAllByRole("row");
  expect(rows[1]).toHaveTextContent("Payments");                       // 50% pass rate
  expect(within(rows[1]).getByRole("link", { name: "Payments" })).toHaveAttribute("href", "/projects/42/cases?feature=Payments");
  expect(rows[2]).toHaveTextContent("Booking");
  expect(rows[rows.length - 1]).toHaveTextContent(/tests without a case/i);
  expect(within(rows[1]).getAllByRole("cell")[7]).toHaveTextContent("1");   // Flaky tests: 8 flips over 19 pairs
});

test("the grouping is a pressed button kept in the URL; folder adds a depth; labels warn that groups overlap", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: "Folder" }));
  expect(screen.getByTestId("search").textContent).toBe("?group=folder");
  expect(screen.getByRole("button", { name: "Folder" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByLabelText("Depth")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Label" }));
  expect(screen.getByText(/groups overlap and are not summed/i)).toBeInTheDocument();
});

test("columns sort with aria-sort", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: "Executions" }));
  expect(screen.getByRole("columnheader", { name: /executions/i })).toHaveAttribute("aria-sort", "descending");
});

test("case-areas failing shows its error here", () => {
  show("", { data: undefined, error: new Error("x"), refetch: vi.fn() });
  expect(screen.getByText("Cases could not be loaded")).toBeInTheDocument();
});

test("the CSV has one row per area", () => {
  const { groups, noCase } = groupByArea(AREAS_FIXTURE, decodeTests(TESTS_REPORT.tests!), "feature", 1);
  const lines = areasCsv(groups, noCase).split("\r\n");
  expect(lines[0]).toBe("area,linked_tests,tests_run,executions,pass_rate,failures,failing_tests,flaky_tests,few_runs");
  expect(lines).toHaveLength(4);                                       // Payments, Booking, No case
});

test("a cut list says so and hides the counts that would be wrong", () => {
  show("", { data: AREAS_FIXTURE, error: null, refetch: vi.fn() },
    { ...TESTS_REPORT, tests: { ...TESTS_REPORT.tests!, truncated: true } });
  expect(screen.getByText(/only the 50,000 with the most failures are grouped/i)).toBeInTheDocument();
  expect(screen.getByText(/never-run and unlinked counts are hidden because the list was cut at 50,000 tests/i)).toBeInTheDocument();
  expect(screen.queryByText(/tests without a case/i)).not.toBeInTheDocument();
});

test("a complete list shows the unlinked row and no cut note", () => {
  show();
  expect(screen.queryByText(/hidden because the list was cut/i)).not.toBeInTheDocument();
});

test("a response without the tests section renders nothing instead of throwing", () => {
  show("", { data: AREAS_FIXTURE, error: null, refetch: vi.fn() }, SUMMARY_REPORT);
  expect(screen.getByRole("heading", { name: "By area" })).toBeInTheDocument();
  expect(screen.queryByRole("table", { name: /by area/i })).not.toBeInTheDocument();
});
