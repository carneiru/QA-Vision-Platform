import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import ProjectLayout from "./ProjectLayout";

test("header shows the project name once loaded", async () => {
  setAccessToken("acc");
  server.use(
    http.get("/api/v1/projects/42", () =>
      HttpResponse.json({ id: 42, name: "Web Tests", organization_id: 1 }),
    ),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/trends"]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectLayout />}>
            <Route path="trends" element={<div>VIEW</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { name: "Web Tests" })).toBeInTheDocument();
});
