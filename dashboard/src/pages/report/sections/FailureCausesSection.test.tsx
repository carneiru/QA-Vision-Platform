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

test("with no failures the resolved list still shows", () => {
  const fc = CAUSES_REPORT.failure_causes!;
  show({ ...CAUSES_REPORT, failure_causes: { ...fc, groups: [], groups_total: 0, failures: 0, other: { groups: 0, occurrences: 0 } } });
  expect(screen.getByText(/no failures in this period/i)).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: /resolved since the previous period/i })).getByText(/ECONNREFUSED/)).toBeInTheDocument();
});

test("no failures and nothing resolved shows only the message", () => {
  const fc = CAUSES_REPORT.failure_causes!;
  show({ ...CAUSES_REPORT, failure_causes: { ...fc, groups: [], groups_total: 0, failures: 0, other: { groups: 0, occurrences: 0 }, resolved: [] } });
  expect(screen.getByText(/no failures in this period/i)).toBeInTheDocument();
  expect(screen.queryByRole("list", { name: /resolved/i })).not.toBeInTheDocument();
});

test("the resolved last seen date uses the same formatting as the other dates", () => {
  show();
  const expected = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(new Date("2026-09-02T10:00:00Z"));
  expect(within(screen.getByRole("list", { name: /resolved since the previous period/i })).getByText(new RegExp(`last seen ${expected}`))).toBeInTheDocument();
});

test("causes sharing a truncated headline render without duplicate key warnings", () => {
  const fc = CAUSES_REPORT.failure_causes!;
  const base = fc.groups[0];
  const long = "x".repeat(100);
  const err = vi.spyOn(console, "error").mockImplementation(() => {});
  show({ ...CAUSES_REPORT, failure_causes: { ...fc, groups: [{ ...base, signature: "s1", headline: `${long}a` }, { ...base, signature: "s2", headline: `${long}b` }] } });
  const dup = err.mock.calls.some((c) => String(c[0]).includes("same key"));
  err.mockRestore();
  expect(dup).toBe(false);
});
