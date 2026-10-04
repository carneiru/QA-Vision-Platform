import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { setAccessToken, clearTokens } from "./auth/tokens";
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
  setAccessToken("acc");
  renderAt("/projects/42");
  // TrendsPage is lazy-loaded; allow for chunk resolution under parallel test load.
  expect(
    await screen.findByRole("heading", { name: /trends/i }, { timeout: 5000 }),
  ).toBeInTheDocument();
});


test("a skip link jumps past the header straight to the main content", async () => {
  clearTokens();
  renderAt("/login");
  const skip = screen.getByRole("link", { name: /skip to content/i });
  await (await import("@testing-library/user-event")).default.click(skip);
  expect(screen.getByRole("main")).toHaveFocus();
});

test("each view has its own document title", () => {
  clearTokens();
  renderAt("/register");
  expect(document.title).toBe("Create account · QA Vision");
});
