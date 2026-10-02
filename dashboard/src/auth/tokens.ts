const REFRESH_KEY = "qav.refresh";
let accessToken: string | null = null;

export function setTokens(access: string, refresh: string): void {
  accessToken = access;
  sessionStorage.setItem(REFRESH_KEY, refresh);
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_KEY);
}

export function clearTokens(): void {
  accessToken = null;
  sessionStorage.removeItem(REFRESH_KEY);
}

export function isAuthenticated(): boolean {
  return getRefreshToken() !== null;
}
