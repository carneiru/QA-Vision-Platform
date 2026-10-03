import { apiFetch } from "./http";

// Types mirror platforms/ingestion-service/src/ingestion/schemas/api_key.py

export interface ApiKey {
  id: number;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

// The only response that ever carries the full key
export interface ApiKeyCreated extends Omit<ApiKey, "last_used_at" | "revoked_at"> {
  key: string;
}

export function listKeys(projectId: number): Promise<ApiKey[]> {
  return apiFetch(`/api/v1/projects/${projectId}/api-keys`);
}

export function createKey(projectId: number, name: string): Promise<ApiKeyCreated> {
  return apiFetch(`/api/v1/projects/${projectId}/api-keys`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export function revokeKey(projectId: number, keyId: number): Promise<void> {
  return apiFetch(`/api/v1/projects/${projectId}/api-keys/${keyId}`, { method: "DELETE" });
}
