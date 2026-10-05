import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

// App boot probes the cookie session; default to "no session" so tests that
// don't care never trip the unhandled-request guard. Tests override as needed.
export const server = setupServer(
  http.post("/api/v1/auth/refresh-token", () => new HttpResponse(null, { status: 401 })),
  // Run pages ask for failure groups; tests about them override this
  http.get("/api/v1/runs/:runId/failure-groups", () => HttpResponse.json({ total: 0, groups: [] })),
);
