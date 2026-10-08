import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "./test/server";
import { setAccessToken } from "./auth/tokens";
import { AppRoutes } from "./App";

/** Every API call fails; the chart views have not been loaded yet in this file. */
function renderAt(path: string) {
  setAccessToken("acc");
  server.use(http.all("/api/v1/*", () => HttpResponse.json({ detail: "not here" }, { status: 404 })));
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("a lazily loaded view still takes focus on its h1 after a navigation", async () => {
  renderAt("/projects/42/overview");
  await screen.findByRole("heading", { level: 1, name: "Overview" });
  await userEvent.click(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Trends" }));
  const h1 = await screen.findByRole("heading", { level: 1, name: "Trends" });
  expect(h1).toHaveFocus();
  // Once the chart code has loaded (it reports the failed request), the same heading keeps focus
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "Trends" })).toHaveFocus();
});
