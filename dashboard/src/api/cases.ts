import { apiFetch, buildQuery } from "./http";

// Mirrors platforms/test-management-service/src/casebook/schemas/{case,suite}.py

export type Priority = "low" | "medium" | "high" | "critical";
export type CaseStatus = "draft" | "ready" | "archived";

export interface Step {
  action: string;
  expected: string;
}

export interface Case {
  number: number;
  /** TC-<number> */
  key: string;
  title: string;
  description: string | null;
  steps: Step[];
  labels: string[];
  priority: Priority;
  status: CaseStatus;
  /** The automated test (ingestion's test_key) this case is implemented by. */
  automated_test_key: string | null;
  automated_name: string | null;
  created_by: number;
  created_at: string;
  updated_by: number | null;
  updated_at: string | null;
  /** Repo-relative .feature path, for a case imported from Gherkin. */
  source_path: string | null;
  gherkin: string | null;
  /** Filled on the single-case read. */
  suites: { id: number; name: string }[];
}

export type CaseInput = Partial<
  Pick<Case, "title" | "description" | "steps" | "labels" | "priority" | "status" | "automated_test_key" | "automated_name">
>;

export interface CaseQuery {
  search?: string;
  label?: string;
  status?: CaseStatus;
  priority?: Priority;
  include_archived?: boolean;
  origin?: "manual" | "imported";
  limit: number;
  offset: number;
}

const base = (projectId: number) => `/api/v1/projects/${projectId}`;

export function listCases(projectId: number, q: CaseQuery): Promise<{ total: number; items: Case[] }> {
  const query = buildQuery({ ...q, include_archived: q.include_archived ? "true" : undefined });
  return apiFetch(`${base(projectId)}/cases${query}`);
}

export function getCase(projectId: number, number: number): Promise<Case> {
  return apiFetch(`${base(projectId)}/cases/${number}`);
}

export function createCase(projectId: number, body: CaseInput): Promise<Case> {
  return apiFetch(`${base(projectId)}/cases`, { method: "POST", body: JSON.stringify(body) });
}

export function updateCase(projectId: number, number: number, changes: CaseInput): Promise<Case> {
  return apiFetch(`${base(projectId)}/cases/${number}`, { method: "PATCH", body: JSON.stringify(changes) });
}

export function listLabels(projectId: number): Promise<{ label: string; count: number }[]> {
  return apiFetch(`${base(projectId)}/case-labels`);
}

export interface Suite {
  id: number;
  name: string;
  description: string | null;
  case_count: number;
  created_at: string;
  updated_at: string | null;
}

export interface SuiteCase {
  number: number;
  key: string;
  title: string;
  status: CaseStatus;
  priority: Priority;
  labels: string[];
  automated_test_key: string | null;
}

export interface SuiteDetail extends Suite {
  cases: SuiteCase[];
}

export function listSuites(projectId: number): Promise<Suite[]> {
  return apiFetch(`${base(projectId)}/suites`);
}

export function getSuite(projectId: number, suiteId: number): Promise<SuiteDetail> {
  return apiFetch(`${base(projectId)}/suites/${suiteId}`);
}

export function createSuite(projectId: number, body: { name: string; description?: string }): Promise<Suite> {
  return apiFetch(`${base(projectId)}/suites`, { method: "POST", body: JSON.stringify(body) });
}

export function updateSuite(
  projectId: number,
  suiteId: number,
  changes: { name?: string; description?: string | null },
): Promise<Suite> {
  return apiFetch(`${base(projectId)}/suites/${suiteId}`, { method: "PATCH", body: JSON.stringify(changes) });
}

/** Replaces the suite's whole ordered list of cases. */
export function setSuiteCases(projectId: number, suiteId: number, numbers: number[]): Promise<SuiteDetail> {
  return apiFetch(`${base(projectId)}/suites/${suiteId}/cases`, { method: "PUT", body: JSON.stringify({ cases: numbers }) });
}

export function deleteSuite(projectId: number, suiteId: number): Promise<void> {
  return apiFetch(`${base(projectId)}/suites/${suiteId}`, { method: "DELETE" });
}

export const PRIORITIES: Priority[] = ["low", "medium", "high", "critical"];
export const STATUSES: CaseStatus[] = ["draft", "ready", "archived"];

/** "checkout, Smoke" -> ["checkout", "smoke"]: what the label field accepts. */
export function parseLabels(text: string): string[] {
  return [...new Set(text.split(/[,\s]+/).map((l) => l.trim().toLowerCase()).filter(Boolean))].sort();
}

export type ImportAction = "create" | "update" | "unchanged" | "move" | "reactivate" | "archive" | "skip";
export interface ImportIssue { path: string; line: number | null; message: string }
export interface ImportItem { action: ImportAction; path: string; scenario: string | null; case_number: number | null }
export interface ImportResult {
  plan_hash: string;
  summary: Record<"created" | "updated" | "moved" | "reactivated" | "archived" | "unchanged" | "skipped", number>;
  items: ImportItem[];
  errors: ImportIssue[];
  warnings: ImportIssue[];
}
export interface ImportFile { path: string; content: string }

/** Plans (dryRun) or applies an import of Gherkin files; apply passes the previewed plan's hash. */
export function importCases(
  projectId: number,
  files: ImportFile[],
  opts: { dryRun: boolean; expectedPlanHash?: string },
): Promise<ImportResult> {
  const body = { files, full: false, ...(opts.expectedPlanHash ? { expected_plan_hash: opts.expectedPlanHash } : {}) };
  return apiFetch(`${base(projectId)}/cases/import?dry_run=${opts.dryRun}`, { method: "POST", body: JSON.stringify(body) });
}
