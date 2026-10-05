import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { getAccessToken, setAccessToken } from "../auth/tokens";
import SecurityPage from "./SecurityPage";

vi.mock("qrcode", () => ({
  default: { toCanvas: vi.fn(async () => {}) },
}));

function renderSecurity() {
  setAccessToken("acc");
  render(
    <MemoryRouter initialEntries={["/account/security"]}>
      <SecurityPage />
    </MemoryRouter>,
  );
}

test("enroll shows the secret and confirm reveals recovery codes", async () => {
  server.use(
    http.post("/api/v1/auth/mfa/enroll", () =>
      HttpResponse.json({ secret: "BASE32SECRET", otpauth_uri: "otpauth://totp/QA%20Vision:a@b.co?secret=BASE32SECRET" }),
    ),
    http.post("/api/v1/auth/mfa/confirm", async ({ request }) => {
      expect(await request.json()).toEqual({ code: "123456" });
      return HttpResponse.json({ recovery_codes: ["aaaa-1111", "bbbb-2222"] });
    }),
  );
  renderSecurity();
  await userEvent.click(await screen.findByRole("button", { name: /set up/i }));
  expect(await screen.findByText("BASE32SECRET")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText(/code/i), "123456");
  await userEvent.click(screen.getByRole("button", { name: /confirm/i }));
  expect(await screen.findByText("aaaa-1111")).toBeInTheDocument();
  expect(screen.getByText(/shown only once/i)).toBeInTheDocument();
});

test("a wrong confirm code surfaces the error", async () => {
  server.use(
    http.post("/api/v1/auth/mfa/enroll", () =>
      HttpResponse.json({ secret: "S", otpauth_uri: "otpauth://totp/x" }),
    ),
    http.post("/api/v1/auth/mfa/confirm", () =>
      HttpResponse.json({ detail: "Invalid code" }, { status: 400 }),
    ),
  );
  renderSecurity();
  await userEvent.click(await screen.findByRole("button", { name: /set up/i }));
  await screen.findByText("S");
  await userEvent.type(screen.getByLabelText(/code/i), "000000");
  await userEvent.click(screen.getByRole("button", { name: /confirm/i }));
  expect(await screen.findByText("Invalid code")).toBeInTheDocument();
});

async function fillChange(current: string, next: string, confirm = next) {
  await userEvent.type(screen.getByLabelText(/current password/i), current);
  await userEvent.type(screen.getByLabelText(/^new password/i), next);
  await userEvent.type(screen.getByLabelText(/confirm new password/i), confirm);
  await userEvent.click(screen.getByRole("button", { name: /change password/i }));
}

test("changing the password sends both and confirms", async () => {
  let sent: unknown = null;
  server.use(
    http.post("/api/v1/auth/change-password", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({ access_token: "new-acc", refresh_token: "r", token_type: "bearer" });
    }),
  );
  renderSecurity();
  await fillChange("old-password-1", "new-password-22");

  expect(await screen.findByText(/password changed/i)).toBeInTheDocument();
  expect(sent).toEqual({ current_password: "old-password-1", new_password: "new-password-22" });
  expect(getAccessToken()).toBe("new-acc");
  // Cleared, so the passwords do not linger in the page
  expect(screen.getByLabelText(/current password/i)).toHaveValue("");
});

test("a wrong current password is reported next to the form", async () => {
  server.use(
    http.post("/api/v1/auth/change-password", () =>
      HttpResponse.json({ detail: "Current password is incorrect" }, { status: 400 })),
  );
  renderSecurity();
  await fillChange("nope-nope-nope", "new-password-22");
  expect(await screen.findByText("Current password is incorrect")).toBeInTheDocument();
});

test("a mismatched confirmation never reaches the server", async () => {
  let called = false;
  server.use(
    http.post("/api/v1/auth/change-password", () => {
      called = true;
      return HttpResponse.json({});
    }),
  );
  renderSecurity();
  await fillChange("old-password-1", "new-password-22", "new-password-23");
  expect(await screen.findByText(/passwords do not match/i)).toBeInTheDocument();
  expect(called).toBe(false);
});
