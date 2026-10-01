import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { setTokens, clearTokens } from "./auth/tokens";
import { AppRoutes } from "./App";
import { MemoryRouter } from "react-router-dom";

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, enabled: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("unauthenticated project route redirects to login", () => {
  clearTokens();
  renderAt("/projects/42/trends");
  expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
});

test("project index redirects to trends tab", async () => {
  setTokens("acc", "ref");
  renderAt("/projects/42");
  expect(await screen.findByRole("heading", { name: /trends/i })).toBeInTheDocument();
});
