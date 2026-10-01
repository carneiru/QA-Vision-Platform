import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens, clearTokens, getRefreshToken } from "../auth/tokens";
import { apiFetch, ApiError, buildQuery, setOnAuthFailure } from "./http";

afterEach(() => clearTokens());

test("buildQuery skips empty values and encodes", () => {
  expect(buildQuery({ days: 30, branch: undefined, search: "" })).toBe("?days=30");
  expect(buildQuery({ q: "a b/c" })).toBe("?q=a%20b%2Fc");
  expect(buildQuery({})).toBe("");
});

test("sends bearer token and parses JSON", async () => {
  setTokens("acc-1", "ref-1");
  server.use(
    http.get("/api/v1/thing", ({ request }) => {
      expect(request.headers.get("Authorization")).toBe("Bearer acc-1");
      return HttpResponse.json({ ok: true });
    }),
  );
  await expect(apiFetch("/api/v1/thing")).resolves.toEqual({ ok: true });
});

test("401 triggers one refresh then retries; concurrent calls share the refresh", async () => {
  setTokens("stale", "ref-1");
  let refreshes = 0;
  server.use(
    http.get("/api/v1/thing", ({ request }) =>
      request.headers.get("Authorization") === "Bearer fresh"
        ? HttpResponse.json({ ok: true })
        : new HttpResponse(null, { status: 401 }),
    ),
    http.post("/api/v1/auth/refresh-token", async ({ request }) => {
      refreshes += 1;
      expect(await request.json()).toEqual({ refresh_token: "ref-1" });
      return HttpResponse.json({ access_token: "fresh", refresh_token: "ref-2", token_type: "bearer" });
    }),
  );
  const [a, b] = await Promise.all([apiFetch("/api/v1/thing"), apiFetch("/api/v1/thing")]);
  expect(a).toEqual({ ok: true });
  expect(b).toEqual({ ok: true });
  expect(refreshes).toBe(1);
  expect(getRefreshToken()).toBe("ref-2"); // rotation stored
});

test("failed refresh clears tokens and calls onAuthFailure", async () => {
  setTokens("stale", "dead");
  const onFail = vi.fn();
  setOnAuthFailure(onFail);
  server.use(
    http.get("/api/v1/thing", () => new HttpResponse(null, { status: 401 })),
    http.post("/api/v1/auth/refresh-token", () => new HttpResponse(null, { status: 401 })),
  );
  await expect(apiFetch("/api/v1/thing")).rejects.toMatchObject({ status: 401 });
  expect(onFail).toHaveBeenCalled();
  expect(getRefreshToken()).toBeNull();
});

test("non-JSON error body becomes a readable ApiError", async () => {
  setTokens("acc", "ref");
  server.use(
    http.get("/api/v1/thing", () => new HttpResponse("<html>Bad Gateway</html>", { status: 502 })),
  );
  const err = await apiFetch("/api/v1/thing").catch((e: unknown) => e as ApiError);
  expect(err).toBeInstanceOf(ApiError);
  expect(err.status).toBe(502);
  expect(err.detail).toMatch(/502/);
});

test("JSON error detail is surfaced", async () => {
  setTokens("acc", "ref");
  server.use(
    http.get("/api/v1/thing", () =>
      HttpResponse.json({ detail: "Project not found" }, { status: 404 }),
    ),
  );
  await expect(apiFetch("/api/v1/thing")).rejects.toMatchObject({ detail: "Project not found" });
});
