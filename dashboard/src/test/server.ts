import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

// App boot probes the cookie session; default to "no session" so tests that
// don't care never trip the unhandled-request guard. Tests override as needed.
export const server = setupServer(
  http.post("/api/v1/auth/refresh-token", () => new HttpResponse(null, { status: 401 })),
  // Run pages ask for failure groups; tests about them override this
  http.get("/api/v1/runs/:runId/failure-groups", () => HttpResponse.json({ total: 0, groups: [] })),
  // The run page looks for the previous run to compare with
  http.get("/api/v1/projects/:projectId/runs", () => HttpResponse.json([])),
  // Run from QEOS: pages that show Play or the run panel ask for these; tests about them override
  http.get("/api/v1/projects/:projectId/ci-target", () =>
    HttpResponse.json({ available: true, configured: false, provider: null, repo: null, workflow: null, ref: null,
      token_last4: null, token_expires_at: null, updated_at: null, last_change: null })),
  http.get("/api/v1/projects/:projectId/run-requests", () => HttpResponse.json({ total: 0, items: [] })),
  // Names of the people who ran or stopped something
  http.get("/api/v1/organizations/:orgId/members", () => HttpResponse.json([])),
);
