import { apiFetch } from "./http";
import { clearTokens, setAccessToken } from "../auth/tokens";

interface TokenOut {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export async function login(email: string, password: string): Promise<void> {
  const tokens = await apiFetch<TokenOut>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  // The refresh token arrives as an httpOnly cookie; only the access token is kept.
  setAccessToken(tokens.access_token);
}

export async function ssoLogin(
  provider: "google" | "microsoft",
  credential: string,
): Promise<void> {
  const tokens = await apiFetch<TokenOut>(`/api/v1/sso/${provider}`, {
    method: "POST",
    body: JSON.stringify({ credential }),
  });
  setAccessToken(tokens.access_token);
}

export async function logout(): Promise<void> {
  try {
    // The cookie identifies the session; the server clears it.
    await apiFetch("/api/v1/auth/logout", { method: "POST", body: "{}" });
  } catch {
    // Best effort: a dead session can't be revoked server-side anyway.
  } finally {
    clearTokens();
  }
}
