import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import RunStrip, { RunStripSkeleton, stripSummary } from "./RunStrip";

const runs = [433, 434, 435, 436].map((id, i) => ({ id, started_at: `2026-10-06T1${i}:02:00Z`, branch: "main" }));

const SUMMARY = "Last 4 runs: 1 passed, 1 failed, 1 re-run, 1 not run";

test("the strip is one link named by the summary, to the newest run with a result", () => {
  render(<MemoryRouter><RunStrip projectId={5} runs={runs} statuses={["passed", "failed", "rerun", null]} /></MemoryRouter>);
  const link = screen.getByRole("link", { name: SUMMARY });
  expect(link).toHaveAttribute("href", "/projects/5/runs/435");
  expect(screen.getAllByRole("link")).toHaveLength(1);
});

test("each bar is a span with a title, and a hidden per-run list follows the link", () => {
  const { container } = render(<MemoryRouter><RunStrip projectId={5} runs={runs} statuses={["passed", "failed", "rerun", "skipped"]} /></MemoryRouter>);
  const bars = container.querySelectorAll("span.run-bar");
  expect(bars).toHaveLength(4);
  expect(bars[1]).toHaveClass("bar-failed");
  expect(bars[1].getAttribute("title")).toMatch(/run #434.*failed/i);
  expect(bars[2]).toHaveClass("bar-rerun");
  expect(bars[3]).toHaveClass("bar-skipped");
  // Outside the link: the link's aria-label would otherwise hide the list from screen readers.
  expect(container.querySelector("a ol")).toBeNull();
  const items = container.querySelectorAll("ol.sr-only li");
  expect(items).toHaveLength(4);
  expect(items[1].textContent).toMatch(/run #434.*failed/i);
  expect(items[2].textContent).toMatch(/run #435.*re-run/i);
});

test("a run the test was not in is an outlined bar", () => {
  const { container } = render(<MemoryRouter><RunStrip projectId={5} runs={runs} statuses={[null, null, null, "passed"]} /></MemoryRouter>);
  expect(container.querySelectorAll("span.run-bar")[0]).toHaveClass("bar-none");
  expect(container.querySelectorAll("li")[0].textContent).toMatch(/run #433.*not run/i);
});

test("a test in none of the runs gets a non-link image with the same label", () => {
  render(<MemoryRouter><RunStrip projectId={5} runs={runs} statuses={[null, null, null, null]} /></MemoryRouter>);
  expect(screen.getByRole("img", { name: "Last 4 runs: 4 not run" })).toBeInTheDocument();
  expect(screen.queryByRole("link")).toBeNull();
});

test("summary only names kinds that occur", () => {
  expect(stripSummary(["passed", "passed"])).toBe("Last 2 runs: 2 passed");
});

test("the skeleton is ten hidden bars with a hidden-text label", () => {
  const { container } = render(<RunStripSkeleton />);
  expect(container.querySelectorAll(".run-bar.bar-loading")).toHaveLength(10);
  expect(screen.getByText("Loading last runs")).toHaveClass("sr-only");
});
