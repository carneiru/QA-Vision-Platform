import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "../auth/tokens";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

let onAuthFailure: () => void = () => {};
export function setOnAuthFailure(fn: () => void): void {
  onAuthFailure = fn;
}

export function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    q.set(key, String(value));
  }
  const s = q.toString();
  // URLSearchParams encodes spaces as "+"; normalize to %20 so paths and
  // params read the same everywhere.
  return s ? `?${s.replaceAll("+", "%20")}` : "";
}

async function errorFrom(response: Response): Promise<ApiError> {
  let detail = `Request failed with status ${response.status}`;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    // non-JSON body (gateway HTML error page): keep the generic detail
  }
  return new ApiError(response.status, detail);
}

// A single in-flight refresh shared by every 401 that hits while it runs.
let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  const response = await fetch("/api/v1/auth/refresh-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!response.ok) return false;
  const body = await response.json();
  setTokens(body.access_token, body.refresh_token);
  return true;
}

async function rawFetch(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return fetch(path, { ...init, headers });
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response = await rawFetch(path, init);

  // Only a session can expire: without a stored refresh token (e.g. a failed
  // login) a 401 is a plain API error, not a refresh trigger.
  if (response.status === 401 && getRefreshToken() !== null) {
    refreshing ??= refreshTokens().finally(() => {
      refreshing = null;
    });
    const refreshed = await refreshing;
    if (!refreshed) {
      clearTokens();
      onAuthFailure();
      throw new ApiError(401, "Session expired");
    }
    response = await rawFetch(path, init);
  }

  if (!response.ok) throw await errorFrom(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
