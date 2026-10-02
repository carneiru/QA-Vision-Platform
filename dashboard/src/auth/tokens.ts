/* The access token lives in memory only. The refresh token never reaches
   JavaScript: it travels as the httpOnly `qav_refresh` cookie the auth
   service sets, scoped to /api/v1/auth. */

let accessToken: string | null = null;

export function setAccessToken(access: string): void {
  accessToken = access;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function clearTokens(): void {
  accessToken = null;
}

export function isAuthenticated(): boolean {
  return accessToken !== null;
}
