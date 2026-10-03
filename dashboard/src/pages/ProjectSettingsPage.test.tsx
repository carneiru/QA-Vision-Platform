import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import ProjectSettingsPage from "./ProjectSettingsPage";

const KEYS = [
  { id: 1, name: "ci", key_prefix: "qav_abcdefgh", created_at: "2026-10-01T10:00:00Z",
    last_used_at: "2026-10-03T10:00:00Z", revoked_at: null },
  { id: 2, name: "old", key_prefix: "qav_zzzzzzzz", created_at: "2026-09-01T10:00:00Z",
    last_used_at: null, revoked_at: "2026-09-15T10:00:00Z" },
];

function renderPage() {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/settings"]}>
        <Routes>
          <Route path="/projects/:projectId/settings" element={<ProjectSettingsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("lists keys with prefix, last use, and revoked state", async () => {
  server.use(http.get("/api/v1/projects/42/api-keys", () => HttpResponse.json(KEYS)));
  renderPage();
  expect(await screen.findByText("qav_abcdefgh…")).toBeInTheDocument();
  expect(screen.getByText("ci")).toBeInTheDocument();
  expect(screen.getByText(/revoked/i)).toBeInTheDocument();
  // a revoked key offers no revoke action
  expect(screen.getAllByRole("button", { name: /revoke/i })).toHaveLength(1);
});

test("creating a key shows the full key exactly once", async () => {
  server.use(
    http.get("/api/v1/projects/42/api-keys", () => HttpResponse.json([])),
    http.post("/api/v1/projects/42/api-keys", () =>
      HttpResponse.json(
        { id: 3, name: "new-ci", key_prefix: "qav_newnewne", key: "qav_newnewnewFULLSECRET",
          created_at: "2026-10-03T12:00:00Z" },
        { status: 201 },
      )),
  );
  renderPage();
  await screen.findByText(/no api keys/i);
  await userEvent.type(screen.getByLabelText(/name/i), "new-ci");
  await userEvent.click(screen.getByRole("button", { name: /create key/i }));
  expect(await screen.findByText("qav_newnewnewFULLSECRET")).toBeInTheDocument();
  expect(screen.getByText(/only shown once/i)).toBeInTheDocument();

  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });
  await userEvent.click(screen.getByRole("button", { name: /copy the api key/i }));
  expect(writeText).toHaveBeenCalledWith("qav_newnewnewFULLSECRET");
});

test("revoking a key calls the API and refreshes", async () => {
  let revoked = false;
  server.use(
    http.get("/api/v1/projects/42/api-keys", () => HttpResponse.json(revoked ? [] : [KEYS[0]])),
    http.delete("/api/v1/projects/42/api-keys/1", () => {
      revoked = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  renderPage();
  await screen.findByText("ci");
  await userEvent.click(screen.getByRole("button", { name: "Revoke key ci" }));
  expect(await screen.findByText(/no api keys/i)).toBeInTheDocument();
  expect(revoked).toBe(true);
});


test("the CI snippet is ready to paste and follows the picked platform", async () => {
  server.use(http.get("/api/v1/projects/42/api-keys", () => HttpResponse.json([])));
  renderPage();
  await screen.findByText(/no api keys/i);

  // GitHub Actions is the default; the snippet carries this deployment's origin
  const snippet = screen.getByTestId("ci-snippet");
  expect(snippet).toHaveTextContent("collector-action@collector-v0.1.0");
  expect(snippet).toHaveTextContent("http://localhost:3000");
  expect(snippet).toHaveTextContent("secrets.QAV_API_KEY");

  await userEvent.selectOptions(screen.getByLabelText(/ci platform/i), "gitlab");
  expect(snippet).toHaveTextContent("qav-collector.gitlab-ci.yml");

  await userEvent.selectOptions(screen.getByLabelText(/ci platform/i), "jenkins");
  expect(snippet).toHaveTextContent("qavCollectorUpload");

  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });
  await userEvent.click(screen.getByRole("button", { name: /copy the ci snippet/i }));
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("qavCollectorUpload"));
});
