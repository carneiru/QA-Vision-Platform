import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../../api/http";
import type { Report } from "../../api/report";
import ReportSection, { type SectionQuery } from "./ReportSection";
import type { Gate } from "./useReportRequest";

const READY: Gate = { state: "ready", base: {} as never, key: [] };
const report = (runs: number) => ({ scope: { runs, previous_runs: 0, test_keys: null } }) as Report;
const q = (over: Partial<SectionQuery>): SectionQuery => ({ data: undefined, error: null, isPending: false, refetch: vi.fn(), ...over });

function show(gate: Gate, query: SectionQuery, reset = vi.fn()) {
  render(
    <ReportSection id="s" title="Summary" gate={gate} query={query} onResetFilters={reset} noRuns={() => <button>Clear filters</button>}>
      {(r) => <p>{r.scope.runs} runs shown</p>}
    </ReportSection>,
  );
  return reset;
}

test("a section is a region named by its heading, with data", () => {
  show(READY, q({ data: report(3) }));
  expect(screen.getByRole("region", { name: "Summary" })).toHaveTextContent("3 runs shown");
});

test("loading while the gate waits or the request runs", () => {
  show({ state: "wait" }, q({ isPending: true }));
  expect(screen.getByRole("status", { name: /loading summary/i })).toBeInTheDocument();
});

test("no runs: says so and offers the section's way out", () => {
  show(READY, q({ data: report(0) }));
  expect(screen.getByText("No runs match these filters in this period")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
});

test("a blocked gate shows its message, with Retry when it carries an error", async () => {
  const retry = vi.fn();
  show({ state: "blocked", message: "Cases could not be loaded", error: new ApiError(500, "boom"), retry }, q({}));
  expect(screen.getByText("Cases could not be loaded")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(retry).toHaveBeenCalled();
});

test("a timeout shows the server's message with Retry", async () => {
  const refetch = vi.fn();
  show(READY, q({ error: new ApiError(503, "This report took too long. Narrow the period or the filters.", "report_timeout"), refetch }));
  expect(screen.getByRole("alert")).toHaveTextContent("This report took too long");
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(refetch).toHaveBeenCalled();
});

test("a 422 names the problem and offers Reset filters", async () => {
  const reset = show(READY, q({ error: new ApiError(422, "from: the period is 95 days") }));
  expect(screen.getByRole("alert")).toHaveTextContent("These filters are not valid: from: the period is 95 days");
  await userEvent.click(screen.getByRole("button", { name: "Reset filters" }));
  expect(reset).toHaveBeenCalled();
});
