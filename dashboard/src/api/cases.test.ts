import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import { listSuites } from "./cases";

beforeEach(() => setAccessToken("acc"));

test("listSuites sends search only when given (an empty one is a 422)", async () => {
  const urls: string[] = [];
  server.use(http.get("/api/v1/projects/42/suites", ({ request }) => { urls.push(request.url); return HttpResponse.json([]); }));
  await listSuites(42);
  await listSuites(42, { search: "" });
  await listSuites(42, { search: "smoke" });
  expect(urls.map((u) => new URL(u).searchParams.get("search"))).toEqual([null, null, "smoke"]);
});

import { getCaseAreas } from "./cases";
import { getRunUrls } from "./runRequests";

test("getCaseAreas maps the short names through the dictionaries", async () => {
  server.use(http.get("/api/v1/projects/42/case-areas", () => HttpResponse.json({
    generated_at: "2026-10-08T14:02:11Z", counts: { cases: 2, linked: 1, manual: 1 },
    folders: ["features/booking"], features: ["Air booking"], labels: ["ado-12", "smoke"],
    suites: [{ id: 12, name: "Regression" }],
    cases: [
      { n: 1, t: "Book", k: "ab".repeat(32), fo: 0, fe: 0, l: [0, 1], s: [0] },
      { n: 4, t: "manual", k: null, fo: null, fe: null, l: [], s: [] },
    ],
  })));
  const areas = await getCaseAreas(42);
  expect(areas.generatedAt).toBe("2026-10-08T14:02:11Z");
  expect(areas.cases[0]).toEqual({ number: 1, title: "Book", testKey: "ab".repeat(32), folder: "features/booking",
    feature: "Air booking", labels: ["ado-12", "smoke"], suiteIds: [12] });
  expect(areas.cases[1]).toEqual({ number: 4, title: "manual", testKey: null, folder: null, feature: null, labels: [], suiteIds: [] });
});

test("getRunUrls asks with since", async () => {
  let since: string | null = null;
  server.use(http.get("/api/v1/projects/42/run-requests/run-urls", ({ request }) => {
    since = new URL(request.url).searchParams.get("since");
    return HttpResponse.json({ urls: ["https://github.com/a/b/actions/runs/1"], truncated: false });
  }));
  expect((await getRunUrls(42, "2026-08-09T00:00:00Z")).urls).toHaveLength(1);
  expect(since).toBe("2026-08-09T00:00:00Z");
});
