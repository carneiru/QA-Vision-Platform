import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import HistoryPage from "./HistoryPage";

const KEY = "tests/a.py::TestLogin::test_ok";

const history = {
  test_key: KEY, suite: "auth", class_name: "TestLogin", name: "test_ok",
  summary: { runs: 3, passed: 2, failed: 1, errored: 0, skipped: 0, pass_rate: 0.667, avg_duration_ms: 500 },
  executions: [
    { run_id: 9, started_at: "2026-09-30T10:00:00Z", branch: "main", commit_sha: "abcdef1234567890",
      environment: "ci", status: "failed", duration_ms: 480,
      message: "AssertionError: expected 200 got 500\n(very long trace)" },
  ],
};

function renderHistory() {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/projects/42/tests/${encodeURIComponent(KEY)}`]}>
        <Routes>
          <Route path="/projects/:projectId/tests/:testKey" element={<HistoryPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("fetches with the encoded key and renders executions", async () => {
  let hit = false;
  server.use(
    http.get(`/api/v1/projects/42/analytics/tests/${encodeURIComponent(KEY)}/history`, () => {
      hit = true;
      return HttpResponse.json(history);
    }),
  );
  renderHistory();
  expect(await screen.findByText("test_ok")).toBeInTheDocument();
  expect(screen.getByText("abcdef1")).toBeInTheDocument(); // short SHA
  expect(hit).toBe(true);
});

test("message is truncated and expandable", async () => {
  server.use(
    http.get(`/api/v1/projects/42/analytics/tests/${encodeURIComponent(KEY)}/history`, () =>
      HttpResponse.json(history),
    ),
  );
  renderHistory();
  await screen.findByText("test_ok");
  expect(screen.queryByText(/very long trace/)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /show full message/i }));
  expect(screen.getByText(/very long trace/)).toBeInTheDocument();
});
