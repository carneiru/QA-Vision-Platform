import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { clearTokens, getAccessToken } from "../auth/tokens";
import VerifyEmailPage from "./VerifyEmailPage";

function renderPage(query = "?token=tok-123") {
  render(
    <MemoryRouter initialEntries={[`/verify-email${query}`]}>
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/" element={<div>PICKER</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

test("a valid token verifies, signs in, and lands on the picker", async () => {
  clearTokens();
  server.use(
    http.get("/api/v1/auth/verify-email", ({ request }) => {
      const token = new URL(request.url).searchParams.get("token");
      if (token !== "tok-123") return HttpResponse.json({ detail: "Invalid token" }, { status: 400 });
      return HttpResponse.json({ access_token: "fresh-acc", refresh_token: "r", token_type: "bearer" });
    }),
  );
  renderPage();
  expect(await screen.findByText("PICKER")).toBeInTheDocument();
  expect(getAccessToken()).toBe("fresh-acc");
});

test("a dead token explains itself and offers registration again", async () => {
  server.use(
    http.get("/api/v1/auth/verify-email", () =>
      HttpResponse.json({ detail: "Invalid or expired token" }, { status: 400 })),
  );
  renderPage();
  expect(await screen.findByText(/invalid or expired/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /register/i })).toBeInTheDocument();
});

test("a missing token never calls the API", async () => {
  renderPage("");
  expect(await screen.findByText(/link is incomplete/i)).toBeInTheDocument();
});
