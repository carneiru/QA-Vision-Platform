import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import ProjectSettingsPage, { isLocalOrigin } from "./ProjectSettingsPage";

const KEYS = [
  { id: 1, name: "ci", key_prefix: "qav_abcdefgh", created_at: "2026-10-01T10:00:00Z",
    last_used_at: "2026-10-03T10:00:00Z", revoked_at: null },
  { id: 2, name: "old", key_prefix: "qav_zzzzzzzz", created_at: "2026-09-01T10:00:00Z",
    last_used_at: null, revoked_at: "2026-09-15T10:00:00Z" },
];

function renderPage(role = "member") {
  setAccessToken("acc");
  server.use(
    http.get("/api/v1/projects/42", () =>
      HttpResponse.json({ id: 42, name: "Web", organization_id: 1, my_role: role })),
    http.get("/api/v1/projects/42/repositories", () => HttpResponse.json([])),
    http.get("/api/v1/projects/42/masking-patterns", () => HttpResponse.json([])),
    http.get("/api/v1/projects/42/notification-channels", () => HttpResponse.json([])),
  );
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

test("repositories come first, editable for members", async () => {
  server.use(http.get("/api/v1/projects/42/api-keys", () => HttpResponse.json([])));
  renderPage("member");
  expect(screen.getAllByRole("heading", { level: 3 })[0]).toHaveTextContent("Repositories");
  expect(await screen.findByLabelText(/repository url/i)).toBeInTheDocument();
});

test("a viewer gets the repositories read-only", async () => {
  server.use(http.get("/api/v1/projects/42/api-keys", () => HttpResponse.json([])));
  renderPage("viewer");
  expect(await screen.findByText(/only owners, admins and members can add or remove repositories/i)).toBeInTheDocument();
  expect(screen.queryByLabelText(/repository url/i)).not.toBeInTheDocument();
});

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
  await userEvent.type(screen.getByPlaceholderText("e.g. github-actions"), "new-ci");
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
  expect(revoked).toBe(false); // the first click only asks
  await userEvent.click(screen.getByRole("button", { name: "Revoke" }));
  expect(await screen.findByText(/no api keys/i)).toBeInTheDocument();
  expect(revoked).toBe(true);
});


test("on localhost the CLI snippet leads, with the self-signed certificate step", async () => {
  server.use(http.get("/api/v1/projects/42/api-keys", () => HttpResponse.json([])));
  renderPage();
  await screen.findByText(/no api keys/i);

  // the test page itself is served from http://localhost:3000
  expect(screen.getByLabelText(/ci platform/i)).toHaveValue("cli");
  const snippet = screen.getByTestId("ci-snippet");
  expect(snippet).toHaveTextContent("qav-collector upload");
  expect(snippet).toHaveTextContent("--ca-file");
  expect(screen.queryByRole("note")).not.toBeInTheDocument();
});

test("hosted CI runners on localhost get a warning, not a silent snippet", async () => {
  server.use(http.get("/api/v1/projects/42/api-keys", () => HttpResponse.json([])));
  renderPage();
  await screen.findByText(/no api keys/i);

  await userEvent.selectOptions(screen.getByLabelText(/ci platform/i), "github");
  expect(screen.getByTestId("ci-snippet")).toHaveTextContent("collector-action@collector-v0.3.0");
  expect(screen.getByRole("note")).toHaveTextContent(/cannot reach localhost/i);

  await userEvent.selectOptions(screen.getByLabelText(/ci platform/i), "gitlab");
  expect(screen.getByRole("note")).toHaveTextContent(/cannot reach localhost/i);

  await userEvent.selectOptions(screen.getByLabelText(/ci platform/i), "azure");
  expect(screen.getByTestId("ci-snippet")).toHaveTextContent("QAV_API_KEY: $(QAV_API_KEY)");
  expect(screen.getByTestId("ci-snippet")).toHaveTextContent("condition: always()");
  expect(screen.getByRole("note")).toHaveTextContent(/cannot reach localhost/i);

  await userEvent.selectOptions(screen.getByLabelText(/ci platform/i), "jenkins");
  expect(screen.getByTestId("ci-snippet")).toHaveTextContent("qavCollectorUpload");

  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });
  await userEvent.click(screen.getByRole("button", { name: /copy the ci snippet/i }));
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("qavCollectorUpload"));
});

test.each([
  ["http://localhost:8080", true],
  ["https://localhost:8443", true],
  ["http://127.0.0.1:5173", true],
  ["http://[::1]:8443", true],
  ["https://qa-vision.example.com", false],
  ["https://localhost.example.com", false],
])("isLocalOrigin(%s) is %s", (origin, expected) => {
  expect(isLocalOrigin(origin)).toBe(expected);
});

test("every CI snippet syncs test cases from .feature files with the pinned collector", async () => {
  server.use(http.get("/api/v1/projects/42/api-keys", () => HttpResponse.json([])));
  renderPage();
  await screen.findByText(/no api keys/i);

  for (const platform of ["github", "gitlab", "azure", "jenkins", "cli"]) {
    await userEvent.selectOptions(screen.getByLabelText(/ci platform/i), platform);
    const snippet = screen.getByTestId("ci-snippet");
    expect(snippet).toHaveTextContent("import-features");
    expect(snippet).toHaveTextContent("collector-v0.3.0");
    if (platform === "jenkins") {
      // Groovy comments are //, never #
      const lines = (snippet.textContent ?? "").split(/\r?\n/).map((l) => l.trim());
      expect(lines.filter((l) => l.startsWith("#"))).toEqual([]);
    }
  }
});
