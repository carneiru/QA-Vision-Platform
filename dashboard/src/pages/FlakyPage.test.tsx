import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import FlakyPage from "./FlakyPage";

const flaky = [
  {
    test_key: "k1", suite: "auth", class_name: "TestLogin", name: "test_ok",
    reason: "same_commit", commits: [{ commit_sha: "abcdef1234", environment: "ci" }],
    flips: null, flip_rate: null, runs: 12, last_status: "passed", last_seen: "2026-09-30T10:00:00Z",
  },
  {
    test_key: "k2", suite: "cart", class_name: "TestCart", name: "test_add",
    reason: "flips", commits: [], flips: 5, flip_rate: 0.42, runs: 12,
    last_status: "failed", last_seen: "2026-09-30T11:00:00Z",
  },
];

function renderFlaky() {
  setTokens("acc", "ref");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/flaky"]}>
        <Routes>
          <Route path="/projects/:projectId/flaky" element={<FlakyPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders confirmed and suspected rows with flip rate", async () => {
  server.use(http.get("/api/v1/projects/42/analytics/flaky", () => HttpResponse.json(flaky)));
  renderFlaky();
  expect(await screen.findByText("Confirmed")).toBeInTheDocument();
  expect(screen.getByText("Suspected")).toBeInTheDocument();
  expect(screen.getByText("42.0%")).toBeInTheDocument();
});

test("controls map to snake_case params", async () => {
  const calls: URLSearchParams[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/flaky", ({ request }) => {
      calls.push(new URL(request.url).searchParams);
      return HttpResponse.json([]);
    }),
  );
  renderFlaky();
  await screen.findByText(/no flaky tests/i);
  await userEvent.selectOptions(screen.getByLabelText(/window/i), "30");
  await screen.findByText(/no flaky tests/i);
  const last = calls[calls.length - 1];
  expect(last.get("window_days")).toBe("30");
  expect(last.get("min_runs")).toBe("5");
  expect(last.get("min_flip_rate")).toBe("0.3");
});
