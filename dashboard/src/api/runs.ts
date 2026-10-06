import { apiFetch, buildQuery } from "./http";

// Types mirror platforms/ingestion-service/src/ingestion/schemas/run.py

export interface Run {
  id: number;
  project_id: number;
  ci_provider: string;
  ci_run_url: string | null;
  commit_sha: string | null;
  branch: string | null;
  environment: string | null;
  agent_version: string | null;
  commit_author: string | null;
  commit_message: string | null;
  pr_number: number | null;
  base_branch: string | null;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  errored: number;
  change_base_ref: string | null;
  changed_files: number | null;
  additions: number | null;
  deletions: number | null;
  changes_truncated: boolean | null;
  created_at: string;
}

export interface ChangedFile {
  path: string;
  status: string;
  additions: number | null;
  deletions: number | null;
}

export interface RunResult {
  id: number;
  test_key: string;
  suite: string;
  class_name: string;
  name: string;
  status: string;
  duration_ms: number;
  message: string | null;
  details: string | null;
  truncated: boolean;
  redacted: boolean;
  file: string | null;
  owner: string | null;
  /** Failed or errored, and the test is in quarantine: shown, not counted. */
  quarantined?: boolean;
}

export interface RunComponent {
  name: string;
  sha: string;
}

export interface RunDetail extends Run {
  /** Failing results of quarantined tests. */
  quarantined?: number;
  /** The failing results that count. */
  blocking?: number;
  results: RunResult[];
  changes: ChangedFile[];
  components: RunComponent[];
}

export type RunStatusFilter = "passed" | "failed" | "skipped" | "errored";

/** Server-side filters for the runs list; every field is optional. */
export interface RunFilters {
  branch?: string;
  status?: "failing" | "passing";
  environment?: string;
  ci_provider?: string;
  commit?: string;
  pr?: number;
  author?: string;
  since?: string; // ISO instant, inclusive
  until?: string; // ISO instant, exclusive
}

export function listRuns(
  projectId: number,
  opts: { limit: number; offset: number } & RunFilters,
): Promise<Run[]> {
  const q = buildQuery({ ...opts });
  return apiFetch(`/api/v1/projects/${projectId}/runs${q}`);
}

export interface GroupedTest {
  id: number;
  test_key: string;
  suite: string;
  class_name: string;
  name: string;
  status: string;
  quarantined?: boolean;
}

/** The cause across this run and up to 19 earlier runs of the same branch. */
export interface CauseHistory {
  window: number;
  seen_in: number;
  /** Consecutive runs up to this one with the cause; 1 means it is new. */
  streak: number;
  since_run_id: number;
  since_started_at: string;
}

/** Failed and errored tests that share one cause: the same error once run-specific values are ignored. */
export interface FailureGroup {
  signature: string;
  /** The first message's first line; null when the tests reported no message. */
  headline: string | null;
  count: number;
  failed: number;
  errored: number;
  quarantined?: number;
  /** The first 100; `count` has them all. */
  tests: GroupedTest[];
  history: CauseHistory;
}

/** What the comparison page shows of each run. */
export type RunOverview = Pick<Run, "id" | "started_at" | "branch" | "commit_sha" | "passed" | "failed" | "errored">;

export interface CompareItem {
  test_key: string;
  suite: string;
  class_name: string;
  name: string;
  base_status: string | null;
  head_status: string | null;
  base_duration_ms: number | null;
  head_duration_ms: number | null;
  message: string | null;
}

export interface RunComparison {
  base: Run;
  head: Run;
  counts: Record<"new_failures" | "fixed" | "still_failing" | "slower" | "added" | "removed" | "unchanged", number>;
  new_failures: CompareItem[];
  fixed: CompareItem[];
  still_failing: CompareItem[];
  slower: CompareItem[];
  added: CompareItem[];
  removed: CompareItem[];
}

/** `head` compared with `base`, test by test (each test's last attempt). */
export function compareRuns(headId: number, baseId: number): Promise<RunComparison> {
  return apiFetch(`/api/v1/runs/${headId}/compare/${baseId}`);
}

export function getFailureGroups(
  runId: number,
): Promise<{ total: number; quarantined?: number; blocking?: number; groups: FailureGroup[] }> {
  return apiFetch(`/api/v1/runs/${runId}/failure-groups`);
}

export function getRun(runId: number, status?: RunStatusFilter): Promise<RunDetail> {
  const q = buildQuery({ status });
  return apiFetch(`/api/v1/runs/${runId}${q}`);
}
