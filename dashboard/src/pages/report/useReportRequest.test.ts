import { ApiError } from "../../api/http";
import type { CaseAreas } from "../../api/cases";
import { parseReportFilters } from "./useReportFilters";
import { caseAreasMessage, computeGate, effectiveBranch, runUrlsSince } from "./useReportRequest";

const TODAY = "2026-10-08";
const filters = (q = "") => parseReportFilters(new URLSearchParams(q), TODAY).filters;
const idle = { data: undefined, error: null, refetch: () => undefined };
const AREAS: CaseAreas = {
  generatedAt: "v1", counts: { cases: 1, linked: 1, manual: 0 }, folders: [], features: ["Booking"], labels: [], suites: [],
  cases: [{ number: 1, title: "a", testKey: "ab".repeat(32), folder: null, feature: "Booking", labels: [], suiteIds: [] }],
};

test("the default branch waits for the repositories; * is every branch", () => {
  expect(computeGate({ filters: filters(), tz: "UTC", defaultBranch: null, caseAreas: idle, runUrls: idle })).toEqual({ state: "wait" });
  expect(effectiveBranch(filters(), "develop")).toBe("develop");
  expect(effectiveBranch(filters("branch=*"), "develop")).toBeNull();
  expect(effectiveBranch(filters("branch=release"), "develop")).toBe("release");
});

test("ready: the request base and a key without the test keys", () => {
  const gate = computeGate({ filters: filters("env=staging"), tz: "Europe/Lisbon", defaultBranch: "main", caseAreas: idle, runUrls: idle });
  expect(gate).toEqual({
    state: "ready",
    base: { from: "2026-09-09", to: TODAY, tz: "Europe/Lisbon", branch: "main", environment: "staging", ci_provider: null,
      origin: "any", requested_run_urls: null, test_keys: null, bucket: "auto" },
    key: [{ from: "2026-09-09", to: TODAY, tz: "Europe/Lisbon", branch: "main", environment: "staging", ci: "", origin: "any",
      area: null, suite: null }, null],
  });
});

test("an area waits for case-areas, then sends its keys and keys the query on the case-areas version", () => {
  const f = filters("area=feature:Booking");
  expect(computeGate({ filters: f, tz: "UTC", defaultBranch: "main", caseAreas: idle, runUrls: idle }).state).toBe("wait");
  const gate = computeGate({ filters: f, tz: "UTC", defaultBranch: "main", caseAreas: { ...idle, data: AREAS }, runUrls: idle });
  expect(gate.state === "ready" && gate.base.test_keys).toEqual(["ab".repeat(32)]);
  expect(gate.state === "ready" && gate.key[1]).toBe("v1");
});

test("an area with no linked tests, too many, or failed case-areas blocks the sections", () => {
  const nothing = computeGate({ filters: filters("area=feature:Nothing"), tz: "UTC", defaultBranch: "main", caseAreas: { ...idle, data: AREAS }, runUrls: idle });
  expect(nothing).toEqual({ state: "blocked", message: "No automated tests are linked to cases in this area" });
  const failed = computeGate({ filters: filters("suite=3"), tz: "UTC", defaultBranch: "main",
    caseAreas: { ...idle, error: new ApiError(409, "x", "too_many_cases") }, runUrls: idle });
  expect(failed).toMatchObject({ state: "blocked", message: "This project has more cases than the report can join (50,000)" });
  expect(caseAreasMessage(new ApiError(500, "boom"))).toBe("Cases could not be loaded");
});

test("origin waits for the Play URLs and never sends the sections unfiltered", () => {
  const f = filters("origin=qeos");
  expect(computeGate({ filters: f, tz: "UTC", defaultBranch: "main", caseAreas: idle, runUrls: idle }).state).toBe("wait");
  expect(computeGate({ filters: f, tz: "UTC", defaultBranch: "main", caseAreas: idle, runUrls: { ...idle, error: new ApiError(500, "down") } }))
    .toMatchObject({ state: "blocked", message: "Play requests could not be loaded" });
  const ready = computeGate({ filters: f, tz: "UTC", defaultBranch: "main", caseAreas: idle, runUrls: { ...idle, data: { urls: ["u"] } } });
  expect(ready.state === "ready" && ready.base.requested_run_urls).toEqual(["u"]);
  expect(runUrlsSince(f)).toBe("2026-08-09T00:00:00Z");  // previous from (2026-08-10) minus one day
});
