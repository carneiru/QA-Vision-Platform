import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
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
      HttpResponse.json({ detail: "Invalid code" }, { status: 401 }),
    ),
  );
  renderSecurity();
  await userEvent.click(await screen.findByRole("button", { name: /set up/i }));
  await screen.findByText("S");
  await userEvent.type(screen.getByLabelText(/code/i), "000000");
  await userEvent.click(screen.getByRole("button", { name: /confirm/i }));
  expect(await screen.findByText("Invalid code")).toBeInTheDocument();
});
