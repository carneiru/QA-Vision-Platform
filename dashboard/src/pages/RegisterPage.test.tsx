import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import RegisterPage from "./RegisterPage";

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/register"]}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

test("registering asks the person to check their email", async () => {
  let sent: { email: string; password: string; full_name?: string } | null = null;
  server.use(
    http.post("/api/v1/auth/register", async ({ request }) => {
      sent = (await request.json()) as typeof sent;
      return HttpResponse.json({ message: "Check your email to complete registration" }, { status: 202 });
    }),
  );
  renderPage();
  await userEvent.type(screen.getByLabelText(/full name/i), "Pedro");
  await userEvent.type(screen.getByLabelText(/email/i), "pedro@example.com");
  await userEvent.type(screen.getByLabelText(/password/i), "UmaPasswordForte123");
  await userEvent.click(screen.getByRole("button", { name: /create account/i }));

  expect(await screen.findByText(/check your email/i)).toBeInTheDocument();
  expect(sent).toEqual({ email: "pedro@example.com", password: "UmaPasswordForte123", full_name: "Pedro" });
  // self-hosted deployments often have no SMTP: say where the link ends up
  expect(screen.getByText(/no email arrives/i)).toBeInTheDocument();
});

test("an already registered email is explained in place", async () => {
  server.use(
    http.post("/api/v1/auth/register", () =>
      HttpResponse.json({ detail: "Email already registered" }, { status: 400 })),
  );
  renderPage();
  await userEvent.type(screen.getByLabelText(/email/i), "pedro@example.com");
  await userEvent.type(screen.getByLabelText(/password/i), "UmaPasswordForte123");
  await userEvent.click(screen.getByRole("button", { name: /create account/i }));
  expect(await screen.findByText(/already registered/i)).toBeInTheDocument();
});

test("links back to sign in", async () => {
  renderPage();
  await userEvent.click(screen.getByRole("link", { name: /sign in/i }));
  expect(await screen.findByText("LOGIN")).toBeInTheDocument();
});

test("the register screen shows the product name and what it stands for", () => {
  renderPage();
  expect(screen.getByRole("heading", { level: 1, name: "QEOS" })).toBeInTheDocument();
  expect(screen.getByText("Quality Engineering OS")).toBeInTheDocument();
});
