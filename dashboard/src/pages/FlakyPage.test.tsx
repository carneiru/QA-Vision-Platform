import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import { downloadCsv } from "../lib/csv";
import FlakyPage from "./FlakyPage";

vi.mock("../lib/csv", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/csv")>()),
  downloadCsv: vi.fn(),
}));

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

test("controls map to snake_case params; window select is immediate", async () => {
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
  await screen.findByText(/last 30 days/i);
  const last = calls[calls.length - 1];
  expect(last.get("window_days")).toBe("30");
  expect(last.get("min_runs")).toBe("5");
  expect(last.get("min_flip_rate")).toBe("0.3");
});

test("Export CSV downloads rows with joined commits", async () => {
  server.use(http.get("/api/v1/projects/42/analytics/flaky", () => HttpResponse.json(flaky)));
  renderFlaky();
  await screen.findByText("Confirmed");
  await userEvent.click(screen.getByRole("button", { name: /export csv/i }));
  await vi.waitFor(() => expect(downloadCsv).toHaveBeenCalled());
  const [filename, csv] = vi.mocked(downloadCsv).mock.calls[0];
  expect(filename).toMatch(/flaky-project-42.*\.csv/);
  expect(csv).toContain("same_commit");
  expect(csv).toContain("abcdef1234:ci");
});

test("numeric inputs apply on submit and clamp to API bounds", async () => {
  const calls: URLSearchParams[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/flaky", ({ request }) => {
      calls.push(new URL(request.url).searchParams);
      return HttpResponse.json([]);
    }),
  );
  renderFlaky();
  await screen.findByText(/no flaky tests/i);
  const fetchesBefore = calls.length;
  const minRuns = screen.getByLabelText(/min runs/i);
  await userEvent.clear(minRuns); // empty mid-edit must not fetch min_runs=0
  expect(calls.length).toBe(fetchesBefore);
  await userEvent.click(screen.getByRole("button", { name: /apply/i }));
  await screen.findByText(/no flaky tests/i);
  const last = calls[calls.length - 1];
  expect(last.get("min_runs")).toBe("2"); // clamped to the API's ge=2
});
