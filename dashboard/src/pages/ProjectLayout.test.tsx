import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import ProjectLayout from "./ProjectLayout";

function renderAt(path: string) {
  setAccessToken("acc");
  server.use(http.get("/api/v1/projects/42", () => HttpResponse.json({ id: 42, name: "Shop E2E" })));
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectLayout />}>
            <Route path="runs" element={<h2>Runs view</h2>} />
            <Route path="settings" element={<h2>Settings view</h2>} />
            <Route path="cases/import" element={<h2>Import view</h2>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("the title names the view and the project", async () => {
  renderAt("/projects/42/runs");
  await screen.findByRole("heading", { name: "Shop E2E" });
  expect(document.title).toBe("Runs · Shop E2E · QA Vision");
});

test("header shows the project name once loaded", async () => {
  renderAt("/projects/42/runs");
  expect(await screen.findByRole("heading", { name: "Shop E2E" })).toBeInTheDocument();
});

test("the import page is titled as such, not as a case number", async () => {
  renderAt("/projects/42/cases/import");
  await screen.findByRole("heading", { name: "Shop E2E" });
  expect(document.title).toBe("Import from Gherkin · Shop E2E · QA Vision");
});
