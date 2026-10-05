import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import ForgotPasswordPage from "./ForgotPasswordPage";

function renderPage(entry: string | { pathname: string; state: unknown } = "/forgot-password") {
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

test("requesting a link sends the email and says where it went", async () => {
  let sent: unknown = null;
  server.use(
    http.post("/api/v1/auth/forgot-password", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({ message: "If an account..." }, { status: 202 });
    }),
  );
  renderPage();
  await userEvent.type(screen.getByLabelText(/email/i), "ada@example.com");
  await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));

  expect(await screen.findByRole("status")).toHaveTextContent(/ada@example\.com/);
  expect(sent).toEqual({ email: "ada@example.com" });
  // No SMTP on a self-hosted deployment: say where the link ends up
  expect(screen.getByText(/no email arrives/i)).toBeInTheDocument();
});

test("the email typed on the sign-in page carries over", () => {
  renderPage({ pathname: "/forgot-password", state: { email: "ada@example.com" } });
  expect(screen.getByLabelText(/email/i)).toHaveValue("ada@example.com");
});

test("a server failure is shown and the form stays usable", async () => {
  server.use(
    http.post("/api/v1/auth/forgot-password", () =>
      HttpResponse.json({ detail: "Too many requests" }, { status: 429 })),
  );
  renderPage();
  await userEvent.type(screen.getByLabelText(/email/i), "ada@example.com");
  await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));
  expect(await screen.findByText(/too many requests/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /send reset link/i })).toBeEnabled();
});

test("links back to sign in", async () => {
  renderPage();
  await userEvent.click(screen.getByRole("link", { name: /back to sign in/i }));
  expect(await screen.findByText("LOGIN")).toBeInTheDocument();
});
