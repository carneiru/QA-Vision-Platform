import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { isAuthenticated, setAccessToken } from "../auth/tokens";
import { logout } from "./auth";

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
