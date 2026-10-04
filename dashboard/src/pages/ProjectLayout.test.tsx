import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

test("following a tab moves focus to the new view's content", async () => {
  renderAt("/projects/42/runs");
  await screen.findByRole("heading", { name: "Shop E2E" });
  await userEvent.click(screen.getByRole("link", { name: "Settings" }));
  expect(await screen.findByText("Settings view")).toBeInTheDocument();
  expect(document.getElementById("content")).toHaveFocus();
  expect(document.title).toBe("Settings · Shop E2E · QA Vision");
});

test("header shows the project name once loaded", async () => {
  renderAt("/projects/42/runs");
  expect(await screen.findByRole("heading", { name: "Shop E2E" })).toBeInTheDocument();
});
