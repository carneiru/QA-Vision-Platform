import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import RunStrip, { RunStripSkeleton, stripSummary } from "./RunStrip";

const runs = [433, 434, 435, 436].map((id, i) => ({ id, started_at: `2026-10-06T1${i}:02:00Z`, branch: "main" }));

test("the strip is a labelled group summarising the runs", () => {
  render(<MemoryRouter><RunStrip projectId={5} runs={runs} statuses={["passed", "failed", "rerun", null]} /></MemoryRouter>);
  expect(screen.getByRole("group", { name: "Last 4 runs: 1 passed, 1 failed, 1 re-run, 1 not run" })).toBeInTheDocument();
});

test("each bar links to its run and says what happened", () => {
  render(<MemoryRouter><RunStrip projectId={5} runs={runs} statuses={["passed", "failed", "rerun", "skipped"]} /></MemoryRouter>);
  const failed = screen.getByRole("link", { name: /run #434.*failed/i });
  expect(failed).toHaveAttribute("href", "/projects/5/runs/434");
  expect(failed).toHaveClass("bar-failed");
  expect(screen.getByRole("link", { name: /run #435.*re-run/i })).toHaveClass("bar-rerun");
  expect(screen.getByRole("link", { name: /run #436.*skipped/i })).toHaveClass("bar-skipped");
});

test("a run the test was not in is an outlined bar", () => {
  render(<MemoryRouter><RunStrip projectId={5} runs={runs} statuses={[null, null, null, "passed"]} /></MemoryRouter>);
  expect(screen.getByRole("link", { name: /run #433.*not run/i })).toHaveClass("bar-none");
});

test("summary only names kinds that occur", () => {
  expect(stripSummary(["passed", "passed"])).toBe("Last 2 runs: 2 passed");
});

test("the skeleton is ten hidden bars with a hidden-text label", () => {
  const { container } = render(<RunStripSkeleton />);
  expect(container.querySelectorAll(".run-bar.bar-loading")).toHaveLength(10);
  expect(screen.getByText("Loading last runs")).toHaveClass("sr-only");
});
