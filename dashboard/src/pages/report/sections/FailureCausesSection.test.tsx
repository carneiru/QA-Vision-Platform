import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { Report } from "../../../api/report";
import type { Gate } from "../useReportRequest";
import { CAUSES_REPORT } from "../testFixtures";
import FailureCausesSection, { causesCsv, truncate } from "./FailureCausesSection";

const READY: Gate = { state: "ready", base: {} as never, key: [] };

function show(report: Report = CAUSES_REPORT) {
  render(
    <MemoryRouter>
      <FailureCausesSection projectId={42} gate={READY} branch="main" onResetFilters={vi.fn()}
        query={{ data: report, error: null, isPending: false, refetch: vi.fn() }} />
    </MemoryRouter>,
  );
}

test("the table tags New and Recurring in words and says when first seen is older than the data read", () => {
  show();
  const table = screen.getByRole("table", { name: /failure causes/i });
  const rows = within(table).getAllByRole("row");
  expect(rows[1]).toHaveTextContent("New");
  expect(rows[2]).toHaveTextContent("Recurring");
  expect(rows[2]).toHaveTextContent(/seen since at least/i);           // first seen in the previous period
  expect(within(rows[1]).getByRole("link", { name: /run #9433/i })).toHaveAttribute("href", "/projects/42/runs/9433");
  expect(within(table).getByText("(no message)")).toBeInTheDocument();
});

test("rows expand to their tests, each linking to its history on the branch", async () => {
  show();
  const toggle = screen.getAllByRole("button", { name: /show tests/i })[0];
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  await userEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", { name: /checkout › Cart › pays/ })).toHaveAttribute(
    "href", `/projects/42/tests/${"a".repeat(64)}?branch=main`);
});

test("chart caption, other causes, resolved list and the sparkline's text", () => {
  show();
  expect(within(screen.getByRole("figure")).getByText(/2,124 failures from 37 causes; the largest is TimeoutError/)).toBeInTheDocument();
  expect(screen.getByText(/34 more causes with 1,617 failures/)).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: /resolved since the previous period/i })).getByText(/ECONNREFUSED/)).toBeInTheDocument();
  expect(screen.getAllByText(/per day: 0, 41/i).length).toBeGreaterThan(0);
});

test("without a previous period every cause is New, with a note", () => {
  show({ ...CAUSES_REPORT, scope: { ...CAUSES_REPORT.scope, previous_runs: 0 } });
  expect(screen.getByText(/no data in the previous period, so every cause is new/i)).toBeInTheDocument();
});

test("CSV columns and headline truncation", () => {
  const lines = causesCsv(CAUSES_REPORT).split("\r\n");
  expect(lines[0]).toBe("signature,headline,occurrences,failed,errored,tests,runs,status,previous_occurrences,first_seen,last_seen");
  expect(lines).toHaveLength(4);
  expect(truncate("x".repeat(100), 80)).toHaveLength(80);
  expect(truncate("short", 80)).toBe("short");
});
