import type { DurationEstimate } from "../api/analytics";
import { approxDuration, estimateText, formatMinutes, requestTiming, runEstimate } from "./durationEstimate";
import type { RunRequest } from "../api/runRequests";

const MIN = 60_000;
const est = (estimate_ms: number | null, upper_ms: number | null, without = 0): DurationEstimate => ({
  estimate_ms, upper_ms, tests_with_history: estimate_ms === null ? 0 : 3, tests_without_history: without, environment_used: 0,
  model: { overhead_ms: 0, factor: 1, runs: 5, fitted: true },
});

test("under a minute reads 'under 1 min'", () => {
  expect(formatMinutes(0)).toBe("under 1 min");
  expect(formatMinutes(59_999)).toBe("under 1 min");
});

test("1 to 90 minutes read as whole minutes", () => {
  expect(formatMinutes(MIN)).toBe("1 min");
  expect(formatMinutes(12 * MIN + 20_000)).toBe("12 min");
  expect(formatMinutes(90 * MIN)).toBe("90 min");
});

test("longer reads hours and minutes", () => {
  expect(formatMinutes(100 * MIN)).toBe("1 h 40 min");
  expect(formatMinutes(91 * MIN)).toBe("1 h 31 min");
  expect(formatMinutes(120 * MIN)).toBe("2 h");
});

test("the main text is the estimate and its upper bound", () => {
  expect(estimateText(est(12 * MIN, 15 * MIN))).toBe("≈ 12 min (up to 15 min)");
  expect(approxDuration(6 * MIN)).toBe("≈ 6 min");
  expect(approxDuration(30_000)).toBe("under 1 min");
});

test("an upper bound that reads the same is not repeated", () => {
  expect(estimateText(est(12 * MIN, 12 * MIN + 10_000))).toBe("≈ 12 min");
});

test("tests without history are counted after the estimate", () => {
  expect(estimateText(est(12 * MIN, 15 * MIN, 3))).toBe("≈ 12 min (up to 15 min) · 3 tests without history");
  expect(estimateText(est(12 * MIN, 15 * MIN, 1))).toBe("≈ 12 min (up to 15 min) · 1 test without history");
});

test("no history at all says so", () => {
  expect(estimateText(est(null, null, 4))).toBe("No history to estimate yet");
});

const request = (over: Partial<RunRequest>): RunRequest => ({
  id: 1, requested_by: 7, requested_at: "2026-10-07T10:00:00Z", selection: [], case_count: 1, suite_id: null,
  status: "running", conclusion: null, github_run_id: null, github_run_url: null, stopped_by: null, stopped_at: null,
  error: null, checked_at: null, skipped_manual: 0, refreshing: true, estimate_ms: 10 * MIN, estimate_upper_ms: 12 * MIN, ...over,
});
const at = (minutes: number) => Date.parse("2026-10-07T10:00:00Z") + minutes * MIN;

test("a running request shows the time left from when it was requested", () => {
  expect(requestTiming(request({}), at(6))).toBe("≈ 4 min left");
  expect(requestTiming(request({}), at(9.5))).toBe("under 1 min left");
});

test("past its estimate a running request says it is running longer", () => {
  expect(requestTiming(request({}), at(11))).toBe("running longer than estimated");
});

test("a completed request compares the estimate with how long it took", () => {
  const done = request({ status: "completed", conclusion: "success", refreshing: false, checked_at: "2026-10-07T10:14:00Z" });
  expect(requestTiming(done, at(30))).toBe("estimated 10 min · took 14 min");
});

test("without an estimate, or in other states, nothing extra shows", () => {
  expect(requestTiming(request({ estimate_ms: null, estimate_upper_ms: null }), at(3))).toBeNull();
  expect(requestTiming(request({ status: "completed", estimate_ms: null, checked_at: "2026-10-07T10:14:00Z" }), at(30))).toBeNull();
  expect(requestTiming(request({ status: "queued" }), at(3))).toBeNull();
  expect(requestTiming(request({ status: "cancelled", checked_at: "2026-10-07T10:14:00Z" }), at(30))).toBeNull();
});

test("what Play stores: the estimate when known and storable, else nothing", () => {
  expect(runEstimate(est(12 * MIN, 15 * MIN))).toEqual({ estimate_ms: 12 * MIN, estimate_upper_ms: 15 * MIN });
  expect(runEstimate(est(null, null))).toBeNull();
  expect(runEstimate(undefined)).toBeNull();
  // test-management takes at most a day: a longer estimate is left out rather than turn Play into a 422
  expect(runEstimate(est(20 * 60 * MIN, 25 * 60 * MIN))).toBeNull();
});

const doneAt = (checked: string | null, extra: Partial<RunRequest> = {}) =>
  request({ status: "completed", conclusion: "success", refreshing: false, checked_at: checked, ...extra });

test("took is the matched QEOS run's own duration, not when the end was seen", () => {
  // Nobody looked for two hours: checked_at is late, the run itself took 13 min
  const late = doneAt("2026-10-07T12:00:00Z");
  expect(requestTiming(late, at(200), { duration_ms: 13 * MIN, started_at: "2026-10-07T10:01:00Z", finished_at: "2026-10-07T10:14:00Z" }))
    .toBe("estimated 10 min · took 13 min");
  // A run without a duration falls back to finished_at − started_at
  expect(requestTiming(late, at(200), { duration_ms: 0, started_at: "2026-10-07T10:01:00Z", finished_at: "2026-10-07T10:09:00Z" }))
    .toBe("estimated 10 min · took 8 min");
});

test("unmatched, took falls back to when the end was seen", () => {
  expect(requestTiming(doneAt("2026-10-07T10:14:00Z"), at(30), undefined)).toBe("estimated 10 min · took 14 min");
});

test("with no real end time, took is left out", () => {
  expect(requestTiming(doneAt(null), at(30))).toBe("estimated 10 min");
});
