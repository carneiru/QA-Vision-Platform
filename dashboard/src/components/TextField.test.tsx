import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TextField from "./TextField";
import NewPasswordFields from "./NewPasswordFields";

function Controlled(props: Partial<React.ComponentProps<typeof TextField>>) {
  const [v, setV] = useState("");
  return <TextField label="Email" type="email" required value={v} onChange={setV} {...props} />;
}

test("an error appears when the field is left, sits outside the label and is linked with aria-describedby", async () => {
  render(<Controlled />);
  const input = screen.getByLabelText("Email");
  await userEvent.type(input, "not-an-email");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument(); // not while typing
  await userEvent.tab();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Enter an email address like name@example.com.");
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(input).toHaveAttribute("aria-describedby", expect.stringContaining(alert.id));
  expect(alert.closest("label")).toBeNull();
  // The label's text is only its own
  expect(screen.getByText("Email", { selector: "label" })).toHaveTextContent(/^Email$/);
  // Fixing it clears the message
  await userEvent.clear(input);
  await userEvent.type(input, "a@b.co");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("a required field left empty says so", async () => {
  render(<Controlled />);
  await userEvent.click(screen.getByLabelText("Email"));
  await userEvent.tab();
  expect(await screen.findByRole("alert")).toHaveTextContent("Email is required.");
});

test("a password field has a Show/Hide toggle that is pressed while the text is visible", async () => {
  render(<Controlled label="Password" type="password" />);
  const input = screen.getByLabelText("Password");
  expect(input).toHaveAttribute("type", "password");
  const toggle = screen.getByRole("button", { name: "Show password" });
  expect(toggle).toHaveAttribute("aria-pressed", "false");
  await userEvent.click(toggle);
  expect(input).toHaveAttribute("type", "text");
  expect(toggle).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(toggle);
  expect(input).toHaveAttribute("type", "password");
});

test("new password: too short is flagged on blur, and the confirmation mismatch on blur too", async () => {
  function Both() {
    const [p, setP] = useState("");
    const [c, setC] = useState("");
    return <NewPasswordFields password={p} confirm={c} onPassword={setP} onConfirm={setC} mismatch={false} />;
  }
  render(<Both />);
  await userEvent.type(screen.getByLabelText("New password"), "short");
  await userEvent.tab();
  expect(await screen.findByText("Use at least 8 characters.")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("New password"), "enough-now");
  await userEvent.type(screen.getByLabelText("Confirm new password"), "different");
  await userEvent.tab();
  const err = await screen.findByText("Passwords do not match.");
  expect(err.closest("label")).toBeNull();
  expect(screen.getByLabelText("Confirm new password")).toHaveAttribute("aria-describedby", expect.stringContaining(err.id));
});
