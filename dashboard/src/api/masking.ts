import { apiFetch } from "./http";

// Mirrors platforms/ingestion-service/src/ingestion/schemas/masking_pattern.py

export interface MaskingPattern {
  id: number;
  name: string;
  pattern: string;
  created_at: string | null;
}

const base = (projectId: number) => `/api/v1/projects/${projectId}/masking-patterns`;

export function listMaskingPatterns(projectId: number): Promise<MaskingPattern[]> {
  return apiFetch(base(projectId));
}

export function addMaskingPattern(projectId: number, name: string, pattern: string): Promise<MaskingPattern> {
  return apiFetch(base(projectId), { method: "POST", body: JSON.stringify({ name, pattern }) });
}

/** The sample as it would be stored with this pattern added (built-in masking included); nothing is saved. */
export function previewMaskingPattern(
  projectId: number,
  name: string,
  pattern: string,
  sample: string,
): Promise<{ masked: string; matches: number }> {
  return apiFetch(`${base(projectId)}/preview`, {
    method: "POST",
    body: JSON.stringify({ name, pattern, sample }),
  });
}

export function removeMaskingPattern(projectId: number, patternId: number): Promise<void> {
  return apiFetch(`${base(projectId)}/${patternId}`, { method: "DELETE" });
}
