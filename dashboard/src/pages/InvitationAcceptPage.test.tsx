import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import InvitationAcceptPage from "./InvitationAcceptPage";

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
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("the preview names the organization and role before accepting", async () => {
  mockPreview();
  renderPage();
  expect(await screen.findByText(/Acme QA/)).toBeInTheDocument();
  expect(screen.getByText(/member/)).toBeInTheDocument();
});

test("accepting joins the organization and links home", async () => {
  mockPreview();
  server.use(
    http.post("/api/v1/invitations/tok-abc123/accept", () =>
      HttpResponse.json(
        { id: 3, organization_id: 7, user_id: 12, role: "member", status: "active",
          created_at: "2026-10-03T11:00:00Z", updated_at: null },
        { status: 201 },
      )),
  );
  renderPage();
  await screen.findByText(/Acme QA/);
  await userEvent.click(screen.getByRole("button", { name: /accept/i }));
  expect(await screen.findByText(/you joined/i)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: /choose a project/i }));
  expect(await screen.findByText("PICKER")).toBeInTheDocument();
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
