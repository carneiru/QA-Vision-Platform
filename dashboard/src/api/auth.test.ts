import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { isAuthenticated, setAccessToken } from "../auth/tokens";
import { login, logout, mfaVerify } from "./auth";

test("login with MFA enabled returns the challenge token, no session", async () => {
  server.use(
    http.post("/api/v1/auth/login", () =>
      HttpResponse.json({ mfa_required: true, mfa_token: "challenge-1" }),
    ),
  );
  const result = await login("a@b.co", "pw");
  expect(result).toEqual({ mfaToken: "challenge-1" });
  expect(isAuthenticated()).toBe(false);
});

test("login without MFA stores the session and returns null", async () => {
  server.use(
    http.post("/api/v1/auth/login", () =>
      HttpResponse.json({ access_token: "acc", refresh_token: "r", token_type: "bearer" }),
    ),
  );
  expect(await login("a@b.co", "pw")).toBeNull();
  expect(isAuthenticated()).toBe(true);
});

test("mfaVerify posts token+code and stores the session", async () => {
  let body: unknown;
  server.use(
    http.post("/api/v1/auth/mfa/verify", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ access_token: "acc2", refresh_token: "r", token_type: "bearer" });
    }),
  );
  await mfaVerify("challenge-1", "123456");
  expect(body).toEqual({ mfa_token: "challenge-1", code: "123456" });
  expect(isAuthenticated()).toBe(true);
});

test("logout posts an empty body (the cookie carries the session) and clears the token", async () => {
  setAccessToken("acc");
  let body: unknown;
  server.use(
    http.post("/api/v1/auth/logout", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ message: "Successfully logged out" });
    }),
  );
  await logout();
  expect(body).toEqual({});
  expect(isAuthenticated()).toBe(false);
});

test("logout clears the session even when the API call fails", async () => {
  setAccessToken("acc");
  server.use(
    http.post("/api/v1/auth/logout", () => new HttpResponse(null, { status: 500 })),
  );
  await expect(logout()).resolves.toBeUndefined();
  expect(isAuthenticated()).toBe(false);
});
