import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { isAuthenticated } from "../auth/tokens";
import { googleEnabled, initGoogleButton, microsoftEnabled } from "../auth/ssoProviders";
import LoginPage from "./LoginPage";

vi.mock("../auth/ssoProviders", () => ({
  googleEnabled: vi.fn(() => false),
  microsoftEnabled: vi.fn(() => false),
  initGoogleButton: vi.fn(async () => {}),
  getMicrosoftCredential: vi.fn(async () => "ms-id-token"),
}));

beforeEach(() => {
  vi.mocked(googleEnabled).mockReturnValue(false);
  vi.mocked(microsoftEnabled).mockReturnValue(false);
  vi.mocked(initGoogleButton).mockClear();
  vi.mocked(initGoogleButton).mockResolvedValue(undefined);
});

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

function ForgotEcho() {
  const { state, search } = useLocation();
  return <div>FORGOT {(state as { email: string }).email}{search}</div>;
}

test("forgot password carries the typed email to the request page", async () => {
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotEcho />} />
      </Routes>
    </MemoryRouter>,
  );
  await userEvent.type(screen.getByLabelText(/email/i), "ada@example.com");
  await userEvent.click(screen.getByRole("link", { name: /forgot password/i }));
  expect(await screen.findByText("FORGOT ada@example.com")).toBeInTheDocument();
});

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
  expect(isAuthenticated()).toBe(true);
});

test("no SSO buttons when providers are unconfigured", () => {
  renderLogin();
  expect(screen.queryByRole("button", { name: /microsoft/i })).not.toBeInTheDocument();
  expect(initGoogleButton).not.toHaveBeenCalled();
});

test("Microsoft sign-in posts the ID token and navigates home", async () => {
  vi.mocked(microsoftEnabled).mockReturnValue(true);
  server.use(
    http.post("/api/v1/sso/microsoft", async ({ request }) => {
      expect(await request.json()).toEqual({ credential: "ms-id-token" });
      return HttpResponse.json({ access_token: "acc", refresh_token: "ref-ms", token_type: "bearer" });
    }),
  );
  renderLogin();
  await userEvent.click(screen.getByRole("button", { name: /microsoft/i }));
  expect(await screen.findByText("PICKER")).toBeInTheDocument();
  expect(isAuthenticated()).toBe(true);
});

test("Microsoft sign-in surfaces the backend's error detail", async () => {
  vi.mocked(microsoftEnabled).mockReturnValue(true);
  server.use(
    http.post("/api/v1/sso/microsoft", () =>
      HttpResponse.json({ detail: "Tenant not allowed" }, { status: 403 }),
    ),
  );
  renderLogin();
  await userEvent.click(screen.getByRole("button", { name: /microsoft/i }));
  expect(await screen.findByText("Tenant not allowed")).toBeInTheDocument();
});

test("Google button mounts and its credential posts to the API", async () => {
  vi.mocked(googleEnabled).mockReturnValue(true);
  let onCredential: ((credential: string) => void) | undefined;
  vi.mocked(initGoogleButton).mockImplementation(async (_el, cb) => {
    onCredential = cb;
  });
  server.use(
    http.post("/api/v1/sso/google", async ({ request }) => {
      expect(await request.json()).toEqual({ credential: "g-id-token" });
      return HttpResponse.json({ access_token: "acc", refresh_token: "ref-g", token_type: "bearer" });
    }),
  );
  renderLogin();
  await vi.waitFor(() => expect(initGoogleButton).toHaveBeenCalled());
  onCredential!("g-id-token");
  expect(await screen.findByText("PICKER")).toBeInTheDocument();
  expect(isAuthenticated()).toBe(true);
});

test("MFA-enabled login asks for a code, then verify signs in", async () => {
  server.use(
    http.post("/api/v1/auth/login", () =>
      HttpResponse.json({ mfa_required: true, mfa_token: "challenge-1" }),
    ),
    http.post("/api/v1/auth/mfa/verify", async ({ request }) => {
      expect(await request.json()).toEqual({ mfa_token: "challenge-1", code: "123456" });
      return HttpResponse.json({ access_token: "acc", refresh_token: "r", token_type: "bearer" });
    }),
  );
  renderLogin();
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.co");
  await userEvent.type(screen.getByLabelText(/password/i), "pw");
  await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));
  await userEvent.type(await screen.findByLabelText(/authentication code/i), "123456");
  await userEvent.click(screen.getByRole("button", { name: /verify/i }));
  expect(await screen.findByText("PICKER")).toBeInTheDocument();
  expect(isAuthenticated()).toBe(true);
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

test("the sign-in screen shows the product name and what it stands for", () => {
  renderLogin();
  expect(screen.getByRole("heading", { level: 1, name: "QEOS" })).toBeInTheDocument();
  expect(screen.getByText("Quality Engineering OS")).toBeInTheDocument();
});
