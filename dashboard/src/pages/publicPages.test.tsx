import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";
import ForgotPasswordPage from "./ForgotPasswordPage";
import ResetPasswordPage from "./ResetPasswordPage";
import VerifyEmailPage from "./VerifyEmailPage";

test.each([
  ["login", <LoginPage />, "/login", "Sign in"],
  ["register", <RegisterPage />, "/register", "Create account"],
  ["forgot password", <ForgotPasswordPage />, "/forgot-password", "Reset your password"],
  ["reset password (no token)", <ResetPasswordPage />, "/reset-password", "Reset link incomplete"],
  ["reset password", <ResetPasswordPage />, "/reset-password?token=t", "Choose a new password"],
  ["verify email (no token)", <VerifyEmailPage />, "/verify-email", "Verification link incomplete"],
])("%s has its own h1, not the product name", (_n, page, url, heading) => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[url]}>{page}</MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  expect(screen.getByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
});
