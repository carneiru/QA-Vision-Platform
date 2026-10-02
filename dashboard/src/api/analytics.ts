import { apiFetch, buildQuery } from "./http";

// Types mirror platforms/ingestion-service/src/ingestion/schemas/analytics.py

export interface TrendDay {
  date: string;
  runs: number;
  total: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  pass_rate: number | null;
  avg_run_duration_ms: number | null;
  max_run_duration_ms: number | null;
}

export type TrendBucket = "day" | "week" | "month";

export interface Trends {
  tz: string;
  bucket: TrendBucket;
  days: TrendDay[];
}

export interface StatsRow {
  test_key: string;
  suite: string;
  class_name: string;
  name: string;
  runs: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  pass_rate: number | null;
  avg_duration_ms: number | null;
  last_status: string;
  last_seen: string;
}

export interface Execution {
  run_id: number;
  started_at: string;
  branch: string | null;
  commit_sha: string | null;
  environment: string | null;
  status: string;
  duration_ms: number;
  message: string | null;
}

export interface History {
  test_key: string;
  suite: string;
  class_name: string;
  name: string;
  summary: {
    runs: number;
    passed: number;
    failed: number;
    errored: number;
    skipped: number;
    pass_rate: number | null;
    avg_duration_ms: number | null;
  };
  executions: Execution[];
}

export interface CommitRef {
  commit_sha: string;
  environment: string | null;
}

export interface FlakyRow {
  test_key: string;
  muted?: boolean;
  suite: string;
  class_name: string;
  name: string;
  reason: "same_commit" | "flips";
  commits: CommitRef[];
  flips: number | null;
  flip_rate: number | null;
  runs: number;
  last_status: string;
  last_seen: string;
}

export function getTrends(
  projectId: number,
  opts: { days: number; tz: string; bucket?: TrendBucket; branch?: string; environment?: string },
): Promise<Trends> {
  const q = buildQuery({
    days: opts.days, tz: opts.tz,
    bucket: opts.bucket && opts.bucket !== "day" ? opts.bucket : undefined,
    branch: opts.branch, environment: opts.environment,
  });
  return apiFetch(`/api/v1/projects/${projectId}/analytics/trends${q}`);
}

export function getTests(
  projectId: number,
  opts: { days: number; sort: "failures" | "duration" | "name"; search?: string; limit: number; offset: number },
): Promise<StatsRow[]> {
  const q = buildQuery({ days: opts.days, sort: opts.sort, search: opts.search, limit: opts.limit, offset: opts.offset });
  return apiFetch(`/api/v1/projects/${projectId}/analytics/tests${q}`);
}

export function getHistory(
  projectId: number,
  testKey: string,
  opts: { days: number; branch?: string; limit: number },
): Promise<History> {
  const q = buildQuery({ days: opts.days, branch: opts.branch, limit: opts.limit });
  return apiFetch(`/api/v1/projects/${projectId}/analytics/tests/${encodeURIComponent(testKey)}/history${q}`);
}

export function muteFlaky(projectId: number, testKey: string): Promise<void> {
  return apiFetch(`/api/v1/projects/${projectId}/analytics/flaky/mute`, {
    method: "PUT",
    body: JSON.stringify({ test_key: testKey }),
  });
}

export function unmuteFlaky(projectId: number, testKey: string): Promise<void> {
  return apiFetch(
    `/api/v1/projects/${projectId}/analytics/flaky/mute/${encodeURIComponent(testKey)}`,
    { method: "DELETE" },
  );
}

export interface BranchStats {
  branch: string | null;
  runs: number;
  total: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  pass_rate: number | null;
  last_seen: string;
}

export function getBranches(
  projectId: number,
  opts: { days: number; limit?: number },
): Promise<BranchStats[]> {
  const q = buildQuery({ days: opts.days, limit: opts.limit });
  return apiFetch(`/api/v1/projects/${projectId}/analytics/branches${q}`);
}

export function getFlaky(
  projectId: number,
  opts: { windowDays: number; minRuns: number; minFlipRate: number; branch?: string; includeMuted?: boolean },
): Promise<FlakyRow[]> {
  const q = buildQuery({
    window_days: opts.windowDays,
    min_runs: opts.minRuns,
    min_flip_rate: opts.minFlipRate,
    branch: opts.branch,
    include_muted: opts.includeMuted ? "true" : undefined,
  });
  return apiFetch(`/api/v1/projects/${projectId}/analytics/flaky${q}`);
}

export function formatPassRate(rate: number | null): string {
  if (rate === null) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

export function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}
