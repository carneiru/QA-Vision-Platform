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
