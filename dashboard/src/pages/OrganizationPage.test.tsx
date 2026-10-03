import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import OrganizationPage from "./OrganizationPage";

const MEMBERS = [
  { id: 1, organization_id: 7, user_id: 10, email: "owner@example.com", role: "owner", status: "active", created_at: "2026-10-01T10:00:00Z", updated_at: null },
  { id: 2, organization_id: 7, user_id: 11, email: null, role: "member", status: "active", created_at: "2026-10-02T10:00:00Z", updated_at: null },
];

const INVITATIONS = [
  { id: 5, organization_id: 7, email: "carol@example.com", role: "member", invited_by_user_id: 10,
    expires_at: "2026-10-10T10:00:00Z", created_at: "2026-10-03T10:00:00Z", accepted_at: null },
];

function mockOrg(role = "owner", invitations = INVITATIONS) {
  server.use(
    http.get("/api/v1/organizations", () =>
      HttpResponse.json([{ id: 7, name: "Acme QA", slug: "acme", role }])),
    http.get("/api/v1/organizations/7/members", () => HttpResponse.json(MEMBERS)),
    http.get("/api/v1/organizations/7/members/me", () => HttpResponse.json({ role })),
    http.get("/api/v1/organizations/7/invitations", () => HttpResponse.json(invitations)),
  );
}

function renderPage() {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/organizations/7"]}>
        <Routes>
          <Route path="/organizations/:orgId" element={<OrganizationPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("lists members and pending invitations", async () => {
  mockOrg();
  renderPage();
  expect(await screen.findByText("Acme QA")).toBeInTheDocument();
  expect(screen.getByText("owner@example.com")).toBeInTheDocument();
  expect(screen.getByText("user 11")).toBeInTheDocument(); // auth had no email: honest fallback
  expect(screen.getByText("carol@example.com")).toBeInTheDocument();
});

test("inviting shows the single-use link with the token", async () => {
  mockOrg();
  server.use(
    http.post("/api/v1/organizations/7/invitations", async ({ request }) => {
      const body = (await request.json()) as { email: string; role: string };
      return HttpResponse.json(
        { id: 6, organization_id: 7, email: body.email, role: body.role, invited_by_user_id: 10,
          token: "tok-abc123", expires_at: "2026-10-10T10:00:00Z", created_at: "2026-10-03T11:00:00Z",
          accepted_at: null },
        { status: 201 },
      );
    }),
  );
  renderPage();
  await screen.findByText("Acme QA");
  await userEvent.type(screen.getByLabelText(/email/i), "dave@example.com");
  await userEvent.selectOptions(screen.getByLabelText(/role/i), "admin");
  await userEvent.click(screen.getByRole("button", { name: /invite/i }));
  const link = await screen.findByText(/\/invitations\/tok-abc123/);
  expect(link).toBeInTheDocument();
  expect(screen.getByText(/only shown once/i)).toBeInTheDocument();

  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });
  await userEvent.click(screen.getByRole("button", { name: /copy the invitation link/i }));
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("/invitations/tok-abc123"));
  expect(await screen.findByRole("button", { name: /copy the invitation link/i })).toHaveTextContent("Copied");
});

test("revoking an invitation calls the API", async () => {
  mockOrg();
  let revoked = false;
  server.use(
    http.delete("/api/v1/organizations/7/invitations/5", () => {
      revoked = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  renderPage();
  await screen.findByText("carol@example.com");
  await userEvent.click(screen.getByRole("button", { name: "Revoke invitation for carol@example.com" }));
  expect(await screen.findByText(/invitation revoked/i)).toBeInTheDocument();
  expect(revoked).toBe(true);
});

test("removing a member calls the API", async () => {
  mockOrg();
  let removed = false;
  server.use(
    http.delete("/api/v1/organizations/7/members/2", () => {
      removed = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  renderPage();
  await screen.findByText("user 11");
  await userEvent.click(screen.getByRole("button", { name: "Remove user 11" }));
  expect(await screen.findByText(/member removed/i)).toBeInTheDocument();
  expect(removed).toBe(true);
});

test("a viewer sees no management controls", async () => {
  mockOrg("viewer", []);
  renderPage();
  await screen.findByText("Acme QA");
  expect(screen.queryByRole("button", { name: /invite/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /remove/i })).not.toBeInTheDocument();
});
