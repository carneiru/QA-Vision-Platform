import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { getRefreshToken, setTokens } from "../auth/tokens";
import { logout } from "./auth";

test("logout clears tokens even when the API call fails", async () => {
  setTokens("acc", "ref-1");
  server.use(
    http.post("/api/v1/auth/logout", () => new HttpResponse(null, { status: 500 })),
  );
  await expect(logout()).resolves.toBeUndefined();
  expect(getRefreshToken()).toBeNull();
});
