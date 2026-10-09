import { apiFetch } from "./http";

// Types mirror platforms/ingestion-service/src/ingestion/schemas/report.py and service/report_service.py
// (spec docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md). Phases 2 and 3 add their sections.

export type ReportSectionName = "summary" | "failure_causes" | "regressions" | "tests" | "duration";
export type ReportOrigin = "any" | "ci" | "qeos";

export interface ReportRequest {
  from: string;
  to: string;
  tz: string;
  branch: string | null;
  environment: string | null;
  ci_provider: string | null;
  origin: ReportOrigin;
  requested_run_urls: string[] | null;
  test_keys: string[] | null;
  sections: ReportSectionName[];
  bucket: "auto" | "day" | "week";
}

export interface ReportPeriod { from: string; to: string; days: number; start: string; end: string }

export interface ReportTotals {
  runs: number;
  executions: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  pass_rate: number | null;
  tests: number;
  failing_tests: number;
  avg_run_duration_ms: number | null;
}

export interface ReportBucket {
  date: string;
  runs: number;
  executions: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  pass_rate: number | null;
}

export interface ReportTestRef { test_key: string; suite: string; class_name: string; name: string }

export interface SummarySection {
  current: ReportTotals;
  previous: ReportTotals | null;
  buckets: ReportBucket[];
  /** The previous period, bucket by bucket: `date` is the previous period's day (plan Ruling 2) */
  previous_buckets: ReportBucket[];
  top_failing: (ReportTestRef & { executions: number; failures: number; pass_rate: number | null })[];
  slowest: (ReportTestRef & { executions: number; avg_duration_ms: number | null })[];
  branches: { branch: string | null; runs: number; executions: number; failures: number; pass_rate: number | null }[];
  facets: { branches: string[]; environments: string[]; ci_providers: string[] };
}

/** Columnar per-test numbers (spec: Section tests); `reportScope.decodeTests` reads them by column name. */
export interface TestsSection { columns: string[]; rows: (string | number | null)[][]; truncated: boolean }

export interface DurationBucket {
  date: string; runs: number; avg_ms: number | null; p50_ms: number | null; p90_ms: number | null; max_ms: number | null;
}
export interface DurationSection {
  basis: "run_wall_time" | "test_time";
  buckets: DurationBucket[];
  previous: { runs: number; avg_ms: number | null; p50_ms: number | null; p90_ms: number | null } | null;
}

export interface Report {
  period: ReportPeriod;
  previous_period: ReportPeriod;
  tz: string;
  bucket: "day" | "week";
  generated_at: string;
  scope: { runs: number; previous_runs: number; test_keys: number | null };
  summary?: SummarySection;
  failure_causes?: FailureCausesSection;
  regressions?: RegressionsSection;
  tests?: TestsSection;
  duration?: DurationSection;
}

export function postReport(projectId: number, body: ReportRequest, init: { signal?: AbortSignal } = {}): Promise<Report> {
  return apiFetch(`/api/v1/projects/${projectId}/analytics/report`, {
    method: "POST", body: JSON.stringify(body), signal: init.signal,
  });
}

export function testLabel(r: { suite: string; class_name: string; name: string }): string {
  return [r.suite, r.class_name, r.name].filter(Boolean).join(" › ");
}

export interface CauseTest extends ReportTestRef { occurrences: number; last_run_id: number }

export interface CauseGroup {
  signature: string;
  headline: string | null;
  occurrences: number;
  failed: number;
  errored: number;
  quarantined: number;
  tests: number;
  runs: number;
  status: "new" | "recurring";
  previous_occurrences: number;
  first_seen: string;
  first_seen_run_id: number;
  last_seen: string;
  last_seen_run_id: number;
  /** One count per bucket, aligned with summary.buckets */
  buckets: number[];
  top_tests: CauseTest[];
}

export interface FailureCausesSection {
  failures: number;
  groups_total: number;
  groups: CauseGroup[];
  other: { groups: number; occurrences: number };
  resolved: { signature: string; headline: string | null; previous_occurrences: number; last_seen: string }[];
}

export interface RegressionItem extends ReportTestRef { branch: string | null }
export interface NewlyFailingItem extends RegressionItem {
  failing_since: string; failing_since_run_id: number; last_passed_at: string; last_passed_run_id: number;
  failures: number; headline: string | null;
}
export interface FixedItem extends RegressionItem {
  fixed_at: string; fixed_run_id: number; failing_since: string; failing_since_bounded: boolean; time_to_fix_ms: number;
}
export interface LongestFailingItem extends RegressionItem {
  failing_since: string; failing_since_bounded: boolean; consecutive_failures: number; last_run_id: number; headline: string | null;
}
export interface RegressionsSection {
  newly_failing: { total: number; items: NewlyFailingItem[] };
  fixed: { total: number; items: FixedItem[] };
  longest_failing: { total: number; items: LongestFailingItem[] };
  time_to_fix: { fixes: number; mean_ms: number | null; median_ms: number | null; p90_ms: number | null; bounded: number };
  flakiness: { date: string; tests_executed: number; flaky_tests: number; flips: number }[];
}
