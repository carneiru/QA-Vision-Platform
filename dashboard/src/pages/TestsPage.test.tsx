import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import TestsPage from "./TestsPage";

const row = (key: string, name: string) => ({
  test_key: key, suite: "auth", class_name: "TestLogin", name,
  runs: 10, passed: 9, failed: 1, errored: 0, skipped: 0,
  pass_rate: 0.9, avg_duration_ms: 420, last_status: "failed", last_seen: "2026-09-30T10:00:00Z",
});

function renderTests() {
  setTokens("acc", "ref");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/tests"]}>
        <Routes>
          <Route path="/projects/:projectId/tests" element={<TestsPage />} />
          <Route path="/projects/:projectId/tests/:testKey" element={<div>HISTORY</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders rows; clicking a test navigates to its encoded history route", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/tests", () =>
      HttpResponse.json([row("tests/a.py::TestLogin::test_ok", "test_ok")]),
    ),
  );
  renderTests();
  await userEvent.click(await screen.findByText("test_ok"));
  expect(await screen.findByText("HISTORY")).toBeInTheDocument();
});

test("search and sort map to params; next page advances offset", async () => {
  const calls: URLSearchParams[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/tests", ({ request }) => {
      calls.push(new URL(request.url).searchParams);
      // A full page signals that "Next" should be enabled.
      return HttpResponse.json(Array.from({ length: 50 }, (_, i) => row(`k${i}`, `t${i}`)));
    }),
  );
  renderTests();
  await screen.findByText("t0");
  await userEvent.selectOptions(screen.getByLabelText(/sort/i), "duration");
  await userEvent.type(screen.getByLabelText(/search/i), "login");
  await userEvent.click(screen.getByRole("button", { name: /apply/i }));
  await userEvent.click(await screen.findByRole("button", { name: /next/i }));
  const last = calls[calls.length - 1];
  expect(last.get("sort")).toBe("duration");
  expect(last.get("search")).toBe("login");
  expect(last.get("offset")).toBe("50");
});

test("empty result shows an empty state", async () => {
  server.use(http.get("/api/v1/projects/42/analytics/tests", () => HttpResponse.json([])));
  renderTests();
  expect(await screen.findByText(/no tests/i)).toBeInTheDocument();
});
