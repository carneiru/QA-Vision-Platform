import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import { getRun, listRuns } from "./runs";

beforeEach(() => setTokens("acc", "ref"));

test("listRuns maps pagination and branch to query params", async () => {
  let url = "";
  server.use(
    http.get("/api/v1/projects/42/runs", ({ request }) => {
      url = request.url;
      return HttpResponse.json([]);
    }),
  );
  await listRuns(42, { limit: 50, offset: 100, branch: "main" });
  const params = new URL(url).searchParams;
  expect(params.get("limit")).toBe("50");
  expect(params.get("offset")).toBe("100");
  expect(params.get("branch")).toBe("main");
});

test("getRun passes the status filter only when set", async () => {
  const urls: string[] = [];
  server.use(
    http.get("/api/v1/runs/9", ({ request }) => {
      urls.push(request.url);
      return HttpResponse.json({
        id: 9, project_id: 42, ci_provider: "github_actions", ci_run_url: null,
        commit_sha: null, branch: null, environment: null, agent_version: null,
        started_at: "2026-10-01T12:00:00Z", finished_at: "2026-10-01T12:04:00Z",
        duration_ms: 240000, total: 0, passed: 0, failed: 0, skipped: 0, errored: 0,
        created_at: "2026-10-01T12:05:00Z", results: [],
      });
    }),
  );
  await getRun(9);
  expect(new URL(urls[0]).searchParams.has("status")).toBe(false);
  await getRun(9, "failed");
  expect(new URL(urls[1]).searchParams.get("status")).toBe("failed");
});
