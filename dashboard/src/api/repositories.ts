import { apiFetch } from "./http";

// Mirrors platforms/project-service/src/project/schemas/repository.py

export type VerificationStatus = "verified" | "not_found" | "unchecked";

export interface Repository {
  id: number;
  project_id: number;
  provider: string;
  owner: string;
  name: string;
  url: string;
  default_branch: string;
  default_branch_is_user_set: boolean;
  verification_status: VerificationStatus;
  verified_at: string | null;
  created_at: string;
  updated_at: string | null;
}

const base = (projectId: number) => `/api/v1/projects/${projectId}/repositories`;

export function listRepositories(projectId: number): Promise<Repository[]> {
  return apiFetch(base(projectId));
}

/** Without a branch the provider's default is used (and kept in sync on re-checks). */
export function addRepository(projectId: number, url: string, defaultBranch?: string): Promise<Repository> {
  const body: Record<string, string> = { url };
  if (defaultBranch) body.default_branch = defaultBranch;
  return apiFetch(base(projectId), { method: "POST", body: JSON.stringify(body) });
}

export function verifyRepository(projectId: number, repoId: number): Promise<Repository> {
  return apiFetch(`${base(projectId)}/${repoId}/verify`, { method: "POST", body: "{}" });
}

export function removeRepository(projectId: number, repoId: number): Promise<void> {
  return apiFetch(`${base(projectId)}/${repoId}`, { method: "DELETE" });
}
