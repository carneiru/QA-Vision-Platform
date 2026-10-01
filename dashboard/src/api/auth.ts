import { apiFetch } from "./http";
import { clearTokens, getRefreshToken, setTokens } from "../auth/tokens";

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
  setTokens(tokens.access_token, tokens.refresh_token);
}

export async function logout(): Promise<void> {
  const refresh = getRefreshToken();
  try {
    if (refresh) {
      await apiFetch("/api/v1/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh }),
      });
    }
  } finally {
    clearTokens();
  }
}
