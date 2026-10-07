import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import { useLocation } from "react-router-dom";
import InvitationAcceptPage from "./InvitationAcceptPage";

function OrgPage() {
  const state = useLocation().state as { notice?: string } | null;
  return <div>ORG PAGE <output data-testid="notice">{state?.notice}</output></div>;
}

const PREVIEW = {
  organization_id: 7,
  organization_name: "Acme QA",
  email: "dave@example.com",
  role: "member",
  expires_at: "2026-10-10T10:00:00Z",
};

function mockPreview() {
  server.use(
    http.get("/api/v1/invitations/tok-abc123", () => HttpResponse.json(PREVIEW)),
  );
}

function renderPage(token = "tok-abc123") {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/invitations/${token}`]}>
        <Routes>
          <Route path="/invitations/:token" element={<InvitationAcceptPage />} />
          <Route path="/" element={<div>PICKER</div>} />
          <Route path="/organizations/:orgId" element={<OrgPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return qc;
}

test("the preview names the organization and role before accepting", async () => {
  mockPreview();
  renderPage();
  expect(await screen.findByText(/Acme QA/)).toBeInTheDocument();
  expect(screen.getByText(/member/)).toBeInTheDocument();
});

test("accepting refreshes the organization and project lists, then opens the new organization", async () => {
  mockPreview();
  server.use(
    http.post("/api/v1/invitations/tok-abc123/accept", () =>
      HttpResponse.json(
        { id: 3, organization_id: 7, user_id: 12, role: "member", status: "active",
          created_at: "2026-10-03T11:00:00Z", updated_at: null },
        { status: 201 },
      )),
  );
  const qc = renderPage();
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  await screen.findByText(/Acme QA/);
  await userEvent.click(screen.getByRole("button", { name: /accept/i }));
  expect(await screen.findByText("ORG PAGE")).toBeInTheDocument();
  const keys = invalidate.mock.calls.map(([filters]) => (filters as { queryKey: unknown[] }).queryKey[0]);
  expect(keys).toEqual(expect.arrayContaining(["orgs", "projects"]));
  // The organization page greets the new member
  expect(screen.getByTestId("notice")).toHaveTextContent("You joined Acme QA as member.");
});

test("a dead token explains itself without an accept button", async () => {
  server.use(
    http.get("/api/v1/invitations/tok-abc123", () =>
      HttpResponse.json({ detail: "Invitation not found" }, { status: 404 })),
  );
  renderPage();
  expect(await screen.findByText(/invitation not found/i)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /accept/i })).not.toBeInTheDocument();
});

test("a failing accept is explained in place", async () => {
  mockPreview();
  server.use(
    http.post("/api/v1/invitations/tok-abc123/accept", () =>
      HttpResponse.json({ detail: "Invitation not found" }, { status: 404 })),
  );
  renderPage();
  await screen.findByText(/Acme QA/);
  await userEvent.click(screen.getByRole("button", { name: /accept/i }));
  expect(await screen.findByText(/invitation not found/i)).toBeInTheDocument();
});
