import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { addDays, parseReportFilters, spanDays, todayIn, useReportFilters } from "./useReportFilters";

const TODAY = "2026-10-08";
const parse = (q: string) => parseReportFilters(new URLSearchParams(q), TODAY);

test("today is the calendar day in the zone", () => {
  const late = new Date("2026-10-08T23:30:00Z");
  expect(todayIn("UTC", late)).toBe("2026-10-08");
  expect(todayIn("Europe/Lisbon", late)).toBe("2026-10-09");
  expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  expect(spanDays("2026-09-09", "2026-10-08")).toBe(30);
});

test("the default is the last 30 days, the default branch, every origin", () => {
  const { filters, dropped } = parse("");
  expect(filters).toEqual({ preset: "30", from: "2026-09-09", to: TODAY, days: 30, branch: "", environment: "", ci: "",
    origin: "any", area: null, suite: null });
  expect(dropped).toEqual([]);
});

test("every filter round-trips from the URL", () => {
  const { filters } = parse("from=2026-09-01&to=2026-09-30&branch=*&env=staging&ci=jenkins&origin=qeos&area=folder:features/booking&suite=12");
  expect(filters).toEqual({ preset: null, from: "2026-09-01", to: "2026-09-30", days: 30, branch: "*", environment: "staging",
    ci: "jenkins", origin: "qeos", area: { kind: "folder", value: "features/booking" }, suite: 12 });
  expect(parse("period=7").filters).toMatchObject({ preset: "7", from: "2026-10-02", to: TODAY, days: 7 });
});

test.each([
  ["period=45", ["period"]],
  ["from=2026-09-30&to=2026-09-01", ["from", "to"]],
  ["from=2026-06-01&to=2026-09-30", ["from", "to"]],     // more than 90 days
  ["from=2026-10-01&to=2026-10-09", ["from", "to"]],     // after today
  ["from=2025-08-01&to=2025-08-05", ["from", "to"]],     // more than 400 days ago
  ["from=2026-02-30&to=2026-03-02", ["from", "to"]],     // not a date
  ["from=2026-09-01", ["from"]],
  ["ci=travis", ["ci"]],
  ["ci=constructor", ["ci"]],
  ["origin=sometimes", ["origin"]],
  ["area=bogus", ["area"]],
  ["suite=abc", ["suite"]],
  [`branch=${"b".repeat(256)}`, ["branch"]],
  [`env=${"e".repeat(101)}`, ["env"]],
])("%s is dropped", (q, dropped) => {
  expect(parse(q).dropped).toEqual(dropped);
});

function Probe() {
  const { filters, update, clearAll, notice, dismissNotice } = useReportFilters("UTC");
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <div>
      <output data-testid="filters">{JSON.stringify(filters)}</output>
      <output data-testid="search">{location.search}</output>
      {notice && <p>Some filters in the link were not valid and were removed <button onClick={dismissNotice}>Dismiss</button></p>}
      <button onClick={() => update({ period: "7" })}>7 days</button>
      <button onClick={() => update({ from: "2026-09-01", to: "2026-09-02" })}>custom</button>
      <button onClick={clearAll}>Clear all</button>
      <button onClick={() => navigate(-1)}>Back</button>
    </div>
  );
}

function renderAt(search: string) {
  render(
    <MemoryRouter initialEntries={["/projects/42/report", `/projects/42/report${search}`]} initialIndex={1}>
      <Routes><Route path="/projects/:projectId/report" element={<Probe />} /></Routes>
    </MemoryRouter>,
  );
}

const read = () => JSON.parse(screen.getByTestId("filters").textContent!);
const search = () => screen.getByTestId("search").textContent;

test("updates write the URL, presets and custom ranges replace each other, Back restores", async () => {
  renderAt("?env=staging");
  await userEvent.click(screen.getByRole("button", { name: "7 days" }));
  expect(search()).toBe("?env=staging&period=7");
  await userEvent.click(screen.getByRole("button", { name: "custom" }));
  expect(search()).toBe("?env=staging&from=2026-09-01&to=2026-09-02");
  await userEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(read().preset).toBe("7");
});

test("Clear all keeps the period and the view settings, and returns to the default branch", async () => {
  renderAt("?period=90&branch=release&ci=jenkins&group=folder");
  await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
  expect(search()).toBe("?period=90&group=folder");
  expect(read().branch).toBe("");
});

test("invalid parameters are removed from the URL with a notice", async () => {
  renderAt("?ci=travis&env=staging");
  expect(await screen.findByText(/some filters in the link were not valid/i)).toBeInTheDocument();
  expect(search()).toBe("?env=staging");
  await act(() => userEvent.click(screen.getByRole("button", { name: "Dismiss" })));
  expect(screen.queryByText(/some filters in the link/i)).not.toBeInTheDocument();
});
