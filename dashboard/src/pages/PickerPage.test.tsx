import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import PickerPage from "./PickerPage";

function renderPicker() {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<PickerPage />} />
          <Route path="/projects/:projectId/trends" element={<div>TRENDS</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const org = { id: 1, name: "Acme", slug: "acme", role: "owner", plan_tier: "free", created_at: "2026-01-01T00:00:00Z", updated_at: null };

test("zero organizations shows an empty state", async () => {
  server.use(http.get("/api/v1/organizations", () => HttpResponse.json([])));
  renderPicker();
  expect(await screen.findByText(/not a member of any organization/i)).toBeInTheDocument();
});

test("sign out is available and returns to login", async () => {
  server.use(
    http.get("/api/v1/organizations", () => HttpResponse.json([])),
    http.post("/api/v1/auth/logout", () => new HttpResponse(null, { status: 200 })),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<PickerPage />} />
          <Route path="/login" element={<div>LOGIN</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  setAccessToken("acc");
  await userEvent.click(await screen.findByRole("button", { name: /sign out/i }));
  expect(await screen.findByText("LOGIN")).toBeInTheDocument();
});

test("selecting an org lists projects; clicking navigates to trends", async () => {
  server.use(
    http.get("/api/v1/organizations", () => HttpResponse.json([org])),
    http.get("/api/v1/organizations/1/projects", () =>
      HttpResponse.json([{ id: 42, name: "Web Tests" }]),
    ),
  );
  renderPicker();
  await userEvent.click(await screen.findByText("Acme"));
  await userEvent.click(await screen.findByText("Web Tests"));
  expect(await screen.findByText("TRENDS")).toBeInTheDocument();
});
