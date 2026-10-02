import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import { fetchAllTests } from "./exportData";

const row = (i: number) => ({
  test_key: `k${i}`, suite: "s", class_name: "c", name: `t${i}`,
  runs: 1, passed: 1, failed: 0, errored: 0, skipped: 0,
  pass_rate: 1, avg_duration_ms: 10, last_status: "passed", last_seen: "2026-10-01T00:00:00Z",
});

test("pages through the API until a short page, carrying filters", async () => {
  setAccessToken("acc");
  const calls: URLSearchParams[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/tests", ({ request }) => {
      const params = new URL(request.url).searchParams;
      calls.push(params);
      const offset = Number(params.get("offset"));
      // 250 rows total: 200 + 50.
      const count = offset === 0 ? 200 : 50;
      return HttpResponse.json(Array.from({ length: count }, (_, i) => row(offset + i)));
    }),
  );
  const rows = await fetchAllTests(42, { days: 30, sort: "failures", search: "login" });
  expect(rows).toHaveLength(250);
  expect(calls).toHaveLength(2);
  expect(calls[0].get("limit")).toBe("200");
  expect(calls[1].get("offset")).toBe("200");
  expect(calls[1].get("search")).toBe("login");
});
