import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken, clearTokens, getAccessToken } from "../auth/tokens";
import { apiFetch, ApiError, bootstrapSession, buildQuery, setOnAuthFailure } from "./http";

afterEach(() => {
  clearTokens();
  setOnAuthFailure(() => {});
});

test("buildQuery skips empty values and encodes", () => {
  expect(buildQuery({ days: 30, branch: undefined, search: "" })).toBe("?days=30");
  expect(buildQuery({ q: "a b/c" })).toBe("?q=a%20b%2Fc");
  expect(buildQuery({})).toBe("");
});

test("sends bearer token and parses JSON", async () => {
  setAccessToken("acc-1");
  server.use(
    http.get("/api/v1/thing", ({ request }) => {
      expect(request.headers.get("Authorization")).toBe("Bearer acc-1");
      return HttpResponse.json({ ok: true });
    }),
  );
  await expect(apiFetch("/api/v1/thing")).resolves.toEqual({ ok: true });
});

test("401 triggers one cookie refresh then retries; concurrent calls share it", async () => {
  setAccessToken("stale");
  let refreshes = 0;
  server.use(
    http.get("/api/v1/thing", ({ request }) =>
      request.headers.get("Authorization") === "Bearer fresh"
        ? HttpResponse.json({ ok: true })
        : new HttpResponse(null, { status: 401 }),
    ),
    http.post("/api/v1/auth/refresh-token", async ({ request }) => {
      refreshes += 1;
      // The browser's httpOnly cookie carries the token; the body is empty JSON.
      expect(await request.json()).toEqual({});
      return HttpResponse.json({ access_token: "fresh", refresh_token: "r2", token_type: "bearer" });
    }),
  );
  const [a, b] = await Promise.all([apiFetch("/api/v1/thing"), apiFetch("/api/v1/thing")]);
  expect(a).toEqual({ ok: true });
  expect(b).toEqual({ ok: true });
  expect(refreshes).toBe(1);
  expect(getAccessToken()).toBe("fresh");
});

test("failed refresh clears the session and calls onAuthFailure", async () => {
  setAccessToken("stale");
  const onFail = vi.fn();
  setOnAuthFailure(onFail);
  server.use(
    http.get("/api/v1/thing", () => new HttpResponse(null, { status: 401 })),
    http.post("/api/v1/auth/refresh-token", () => new HttpResponse(null, { status: 401 })),
  );
  await expect(apiFetch("/api/v1/thing")).rejects.toMatchObject({ status: 401 });
  expect(onFail).toHaveBeenCalled();
  expect(getAccessToken()).toBeNull();
});

test("a 401 from an auth endpoint itself never enters the refresh flow", async () => {
  let refreshes = 0;
  server.use(
    http.post("/api/v1/auth/login", () =>
      HttpResponse.json({ detail: "Incorrect email or password" }, { status: 401 }),
    ),
    http.post("/api/v1/auth/refresh-token", () => {
      refreshes += 1;
      return new HttpResponse(null, { status: 401 });
    }),
  );
  await expect(apiFetch("/api/v1/auth/login", { method: "POST", body: "{}" })).rejects.toMatchObject(
    { detail: "Incorrect email or password" },
  );
  expect(refreshes).toBe(0);
});

test("bootstrapSession restores the access token from the cookie session", async () => {
  server.use(
    http.post("/api/v1/auth/refresh-token", () =>
      HttpResponse.json({ access_token: "booted", refresh_token: "r", token_type: "bearer" }),
    ),
  );
  await bootstrapSession();
  expect(getAccessToken()).toBe("booted");
});

test("bootstrapSession without a valid cookie resolves quietly", async () => {
  const onFail = vi.fn();
  setOnAuthFailure(onFail);
  server.use(
    http.post("/api/v1/auth/refresh-token", () => new HttpResponse(null, { status: 401 })),
  );
  await expect(bootstrapSession()).resolves.toBeUndefined();
  expect(getAccessToken()).toBeNull();
  expect(onFail).not.toHaveBeenCalled();
});

test("non-JSON error body becomes a readable ApiError", async () => {
  setAccessToken("acc");
  server.use(
    http.get("/api/v1/thing", () => new HttpResponse("<html>Bad Gateway</html>", { status: 502 })),
  );
  const err: ApiError = await apiFetch("/api/v1/thing").then(
    () => {
      throw new Error("expected apiFetch to reject");
    },
    (e: ApiError) => e,
  );
  expect(err).toBeInstanceOf(ApiError);
  expect(err.status).toBe(502);
  expect(err.detail).toMatch(/502/);
});

test("JSON error detail is surfaced", async () => {
  setAccessToken("acc");
  server.use(
    http.get("/api/v1/thing", () =>
      HttpResponse.json({ detail: "Project not found" }, { status: 404 }),
    ),
  );
  await expect(apiFetch("/api/v1/thing")).rejects.toMatchObject({ detail: "Project not found" });
});
