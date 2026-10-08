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
          <Route path="/projects/:projectId/overview" element={<div>OVERVIEW</div>} />
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

test("every organization lists its projects; a project opens on its overview", async () => {
  server.use(
    http.get("/api/v1/organizations", () => HttpResponse.json([org])),
    http.get("/api/v1/organizations/1/projects", () =>
      HttpResponse.json([{ id: 42, name: "Web Tests" }]),
    ),
  );
  renderPicker();
  // no org to click first: projects are visible straight away
  await userEvent.click(await screen.findByRole("link", { name: "Web Tests" }));
  expect(await screen.findByText("OVERVIEW")).toBeInTheDocument();
});


test("creating an organization refreshes the list", async () => {
  const orgs: object[] = [];
  server.use(
    http.get("/api/v1/organizations", () => HttpResponse.json(orgs)),
    http.post("/api/v1/organizations", async ({ request }) => {
      const body = (await request.json()) as { name: string; slug: string };
      orgs.push({ ...org, id: 9, name: body.name, slug: body.slug });
      return HttpResponse.json({ id: 9, name: body.name, slug: body.slug }, { status: 201 });
    }),
  );
  renderPicker();
  await screen.findByText(/not a member of any organization/i);
  await userEvent.click(screen.getByRole("button", { name: /new organization/i }));
  await userEvent.type(screen.getByLabelText(/name/i), "Minha Org!");
  // the slug is derived from the name, lowercased and dash-safe, but editable
  expect(screen.getByLabelText(/slug/i)).toHaveValue("minha-org");
  await userEvent.click(screen.getByRole("button", { name: /^create organization$/i }));
  expect(await screen.findByText("Minha Org!")).toBeInTheDocument();
});

test("creating a project in an organization", async () => {
  const projects: object[] = [];
  server.use(
    http.get("/api/v1/organizations", () => HttpResponse.json([org])),
    http.get("/api/v1/organizations/1/projects", () => HttpResponse.json(projects)),
    http.post("/api/v1/organizations/1/projects", async ({ request }) => {
      const body = (await request.json()) as { name: string };
      projects.push({ id: 5, name: body.name });
      return HttpResponse.json({ id: 5, name: body.name }, { status: 201 });
    }),
  );
  renderPicker();
  await screen.findByText(/no projects/i);
  await userEvent.click(screen.getByRole("button", { name: /new project/i }));
  await userEvent.type(screen.getByLabelText(/project name/i), "Web Tests");
  await userEvent.click(screen.getByRole("button", { name: /^create project$/i }));
  expect(await screen.findByText("Web Tests")).toBeInTheDocument();
});

test("cancelling the new-project form returns focus to the button that opened it", async () => {
  server.use(
    http.get("/api/v1/organizations", () => HttpResponse.json([org])),
    http.get("/api/v1/organizations/1/projects", () => HttpResponse.json([])),
  );
  renderPicker();
  await screen.findByText(/no projects/i);
  await userEvent.click(screen.getByRole("button", { name: /new project/i }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("button", { name: /new project/i })).toHaveFocus();
});
