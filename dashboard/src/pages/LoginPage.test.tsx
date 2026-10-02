import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { getRefreshToken } from "../auth/tokens";
import LoginPage from "./LoginPage";

function renderLogin() {
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<div>PICKER</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

test("successful login stores tokens and navigates home", async () => {
  server.use(
    http.post("/api/v1/auth/login", async ({ request }) => {
      expect(await request.json()).toEqual({ email: "a@b.co", password: "pw" });
      return HttpResponse.json({ access_token: "acc", refresh_token: "ref", token_type: "bearer" });
    }),
  );
  renderLogin();
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.co");
  await userEvent.type(screen.getByLabelText(/password/i), "pw");
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByText("PICKER")).toBeInTheDocument();
  expect(getRefreshToken()).toBe("ref");
});

test("bad credentials show the API detail", async () => {
  server.use(
    http.post("/api/v1/auth/login", () =>
      HttpResponse.json({ detail: "Incorrect email or password" }, { status: 401 }),
    ),
  );
  renderLogin();
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.co");
  await userEvent.type(screen.getByLabelText(/password/i), "nope");
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByText("Incorrect email or password")).toBeInTheDocument();
});
