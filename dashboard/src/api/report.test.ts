import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import { postReport, testLabel, type ReportRequest } from "./report";

beforeEach(() => setAccessToken("acc"));

const BODY: ReportRequest = {
  from: "2026-09-09", to: "2026-10-08", tz: "Europe/Lisbon", branch: "main", environment: null, ci_provider: null,
  origin: "any", requested_run_urls: null, test_keys: null, sections: ["summary"], bucket: "auto",
};

test("postReport sends the body as JSON to the project's report", async () => {
  let seen: unknown = null;
  server.use(http.post("/api/v1/projects/42/analytics/report", async ({ request }) => {
    seen = await request.json();
    return HttpResponse.json({ scope: { runs: 0, previous_runs: 0, test_keys: null } });
  }));
  const report = await postReport(42, BODY);
  expect(seen).toEqual(BODY);
  expect(report.scope.runs).toBe(0);
});

test("a 503 report_timeout keeps its code", async () => {
  server.use(http.post("/api/v1/projects/42/analytics/report", () => HttpResponse.json(
    { detail: { code: "report_timeout", message: "This report took too long. Narrow the period or the filters." } },
    { status: 503 })));
  await expect(postReport(42, BODY)).rejects.toMatchObject({ status: 503, code: "report_timeout" });
});

test("testLabel joins suite, class and name", () => {
  expect(testLabel({ suite: "checkout", class_name: "", name: "pays" })).toBe("checkout › pays");
});
