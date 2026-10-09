import type { CaseAreas } from "../../api/cases";
import type { CauseGroup, Report, ReportBucket, ReportTotals } from "../../api/report";

const bucket = (date: string, over: Partial<ReportBucket> = {}): ReportBucket => ({
  date, runs: 14, executions: 3301, passed: 3200, failed: 70, errored: 3, skipped: 28, pass_rate: 0.9776, ...over,
});

const totals = (over: Partial<ReportTotals> = {}): ReportTotals => ({
  runs: 412, executions: 98234, passed: 95010, failed: 2011, errored: 113, skipped: 1100, pass_rate: 0.9781,
  tests: 1003, failing_tests: 61, avg_run_duration_ms: 734000, ...over,
});

/** A 30-day report: pass rate up 1.2 pts, failures down 14%, average run time up 5% (the spec's examples). */
export const SUMMARY_REPORT: Report = {
  period: { from: "2026-09-09", to: "2026-10-08", days: 30, start: "2026-09-08T23:00:00Z", end: "2026-10-08T23:00:00Z" },
  previous_period: { from: "2026-08-10", to: "2026-09-08", days: 30, start: "2026-08-09T23:00:00Z", end: "2026-09-08T23:00:00Z" },
  tz: "Europe/Lisbon",
  bucket: "day",
  generated_at: "2026-10-08T14:02:11Z",
  scope: { runs: 412, previous_runs: 398, test_keys: null },
  summary: {
    current: totals(),
    previous: totals({ runs: 398, executions: 95000, failed: 2400, errored: 70, pass_rate: 0.9661, failing_tests: 70, avg_run_duration_ms: 700000 }),
    buckets: [bucket("2026-10-07"), bucket("2026-10-08", { failed: 140, pass_rate: 0.95 })],
    previous_buckets: [bucket("2026-09-07", { pass_rate: 0.97 }), bucket("2026-09-08", { pass_rate: null, runs: 0 })],
    top_failing: [{ test_key: "a".repeat(64), suite: "checkout", class_name: "Cart", name: "pays", executions: 30, failures: 12, pass_rate: 0.6 }],
    slowest: [{ test_key: "b".repeat(64), suite: "checkout", class_name: "Cart", name: "slow one", executions: 30, avg_duration_ms: 81000 }],
    branches: [{ branch: "main", runs: 120, executions: 30120, failures: 400, pass_rate: 0.986 }],
    facets: { branches: ["main", "release/2.4"], environments: ["staging"], ci_providers: ["github_actions"] },
  },
};

/** No runs match: the summary still carries facets, for the suggestions. */
export function emptyReport(): Report {
  return {
    ...SUMMARY_REPORT,
    scope: { runs: 0, previous_runs: 0, test_keys: null },
    summary: { ...SUMMARY_REPORT.summary!, current: totals({ runs: 0, executions: 0, pass_rate: null }), previous: null },
  };
}

const cause = (over: Partial<CauseGroup>): CauseGroup => ({
  signature: "9f2c1ab04e7d", headline: "TimeoutError: locator('#pay-button') after 30000 ms", occurrences: 412, failed: 400,
  errored: 12, quarantined: 0, tests: 18, runs: 66, status: "new", previous_occurrences: 0,
  first_seen: "2026-09-14T08:12:00Z", first_seen_run_id: 9012, last_seen: "2026-10-08T09:40:00Z", last_seen_run_id: 9433,
  buckets: [0, 41], top_tests: [{ test_key: "a".repeat(64), suite: "checkout", class_name: "Cart", name: "pays", occurrences: 40, last_run_id: 9433 }],
  ...over,
});

export const CAUSES_REPORT: Report = {
  ...SUMMARY_REPORT,
  failure_causes: {
    failures: 2124, groups_total: 37,
    groups: [
      cause({}),
      cause({ signature: "11aa22bb33cc", headline: "AssertionError: expected 3 got 4", occurrences: 90, status: "recurring",
        previous_occurrences: 31, first_seen: "2026-08-12T10:00:00Z", buckets: [3, 2] }),
      cause({ signature: "none", headline: null, occurrences: 5, status: "recurring", previous_occurrences: 2 }),
    ],
    other: { groups: 34, occurrences: 1617 },
    resolved: [{ signature: "ffee", headline: "Error: connect ECONNREFUSED", previous_occurrences: 31, last_seen: "2026-09-02T10:00:00Z" }],
  },
};

const ref = (name: string) => ({ test_key: name.padEnd(64, "0"), suite: "checkout", class_name: "Cart", name, branch: "main" });

export const REGRESSIONS_REPORT: Report = {
  ...SUMMARY_REPORT,
  regressions: {
    newly_failing: { total: 9, items: [{ ...ref("pays"), failing_since: "2026-10-02T10:00:00Z", failing_since_run_id: 9301,
      last_passed_at: "2026-09-25T10:00:00Z", last_passed_run_id: 9290, failures: 4, headline: "AssertionError: total" }] },
    fixed: { total: 5, items: [{ ...ref("ships"), fixed_at: "2026-10-04T10:00:00Z", fixed_run_id: 9400,
      failing_since: "2026-10-02T10:00:00Z", failing_since_bounded: true, time_to_fix_ms: 172_800_000 }] },
    longest_failing: { total: 12, items: [{ ...ref("refunds"), failing_since: "2026-09-08T23:00:00Z", failing_since_bounded: true,
      consecutive_failures: 31, last_run_id: 9433, headline: "Error: refund API down" }] },
    time_to_fix: { fixes: 23, mean_ms: 151_200_000, median_ms: 86_400_000, p90_ms: 432_000_000, bounded: 2 },
    flakiness: [{ date: "2026-10-07", tests_executed: 990, flaky_tests: 14, flips: 51 }, { date: "2026-10-08", tests_executed: 0, flaky_tests: 0, flips: 0 }],
  },
};

const key = (n: number) => n.toString(16).padStart(64, "0");

export const AREAS_FIXTURE: CaseAreas = {
  generatedAt: "v1", counts: { cases: 4, linked: 3, manual: 1 },
  folders: ["features/booking", "features/payments"], features: ["Booking", "Payments"], labels: ["smoke"],
  suites: [{ id: 12, name: "Regression" }],
  cases: [
    { number: 1, title: "Book one-way", testKey: key(1), folder: "features/booking", feature: "Booking", labels: ["smoke"], suiteIds: [12] },
    { number: 2, title: "Pay by card", testKey: key(2), folder: "features/payments", feature: "Payments", labels: [], suiteIds: [12] },
    { number: 3, title: "Refund", testKey: key(3), folder: "features/payments", feature: "Payments", labels: [], suiteIds: [] },
    { number: 4, title: "Manual check", testKey: null, folder: null, feature: null, labels: [], suiteIds: [] },
  ],
};

export const TESTS_REPORT: Report = {
  ...SUMMARY_REPORT,
  tests: {
    columns: ["test_key", "executions", "passed", "failed", "errored", "skipped", "flips", "pairs", "duration_ms_sum", "last_status"],
    rows: [[key(1), 30, 30, 0, 0, 0, 0, 29, 90000, "passed"], [key(2), 20, 10, 10, 0, 0, 8, 19, 400000, "failed"],
           [key(9), 5, 5, 0, 0, 0, 0, 4, 1000, "passed"]],
    truncated: false,
  },
  duration: {
    basis: "run_wall_time",
    buckets: [{ date: "2026-10-07", runs: 41, avg_ms: 702000, p50_ms: 650000, p90_ms: 1100000, max_ms: 1500000 },
              { date: "2026-10-08", runs: 0, avg_ms: null, p50_ms: null, p90_ms: null, max_ms: null }],
    previous: { runs: 398, avg_ms: 690000, p50_ms: 640000, p90_ms: 1050000 },
  },
};
