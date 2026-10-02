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
  started_at: string;
  finished_at: string;
  duration_ms: number;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  errored: number;
  created_at: string;
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
}

export interface RunDetail extends Run {
  results: RunResult[];
}

export type RunStatusFilter = "passed" | "failed" | "skipped" | "errored";

export function listRuns(
  projectId: number,
  opts: { limit: number; offset: number; branch?: string },
): Promise<Run[]> {
  const q = buildQuery({ limit: opts.limit, offset: opts.offset, branch: opts.branch });
  return apiFetch(`/api/v1/projects/${projectId}/runs${q}`);
}

export function getRun(runId: number, status?: RunStatusFilter): Promise<RunDetail> {
  const q = buildQuery({ status });
  return apiFetch(`/api/v1/runs/${runId}${q}`);
}
