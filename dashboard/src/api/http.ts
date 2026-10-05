import { clearTokens, getAccessToken, setAccessToken } from "../auth/tokens";

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
  // The httpOnly cookie carries the refresh token; the body stays empty.
  const response = await fetch("/api/v1/auth/refresh-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!response.ok) return false;
  const body = await response.json();
  setAccessToken(body.access_token);
  return true;
}

function sharedRefresh(): Promise<boolean> {
  refreshing ??= refreshTokens().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/** Restores the session from the cookie at app start; quiet on failure. */
export async function bootstrapSession(): Promise<void> {
  if (getAccessToken() !== null) return;
  try {
    await sharedRefresh();
  } catch {
    // Network trouble at boot: the login page is the fallback either way.
  }
}

// Endpoints a person calls to get (or end) a session: their 401 means "wrong
// credentials", never "your access token expired". Every other route,
// including signed-in auth routes like change-password, refreshes on 401.
const SIGN_IN_PATHS = [
  "/api/v1/auth/login",
  "/api/v1/auth/mfa/verify",
  "/api/v1/auth/refresh-token",
  "/api/v1/auth/logout",
  "/api/v1/auth/register",
  "/api/v1/auth/verify-email",
  "/api/v1/auth/resend-verification",
  "/api/v1/auth/forgot-password",
  "/api/v1/auth/reset-password",
];

function isAuthPath(path: string): boolean {
  const route = path.split("?")[0];
  return SIGN_IN_PATHS.includes(route) || route.startsWith("/api/v1/sso/");
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

  // A 401 from login/refresh/logout/sso is that endpoint's own verdict, not
  // an expired session.
  if (response.status === 401 && !isAuthPath(path)) {
    const refreshed = await sharedRefresh();
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
