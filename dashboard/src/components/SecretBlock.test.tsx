import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SecretBlock from "./SecretBlock";

function setClipboard(writeText: (t: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

test("shows the value in a labelled group with the shown-once note", () => {
  render(<SecretBlock label="Key ci" value="qeos_SECRET" copyLabel="Copy key ci" copyText="Copy key" />);
  const group = screen.getByRole("group", { name: "Key ci" });
  expect(group).toHaveTextContent("qeos_SECRET");
  expect(group).toHaveTextContent(/this is shown once/i);
  expect(group).toHaveClass("secret-block");
  expect(screen.getByText("qeos_SECRET")).toHaveClass("secret-value");
});

test("Copy writes the value and announces Copied in a polite live region", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  setClipboard(writeText);
  render(<SecretBlock label="Key ci" value="qeos_SECRET" copyLabel="Copy key ci" copyText="Copy key" />);
  const live = screen.getByRole("status");
  expect(live).toHaveAttribute("aria-live", "polite");
  expect(live).toHaveTextContent("");
  await userEvent.click(screen.getByRole("button", { name: "Copy key ci" }));
  expect(writeText).toHaveBeenCalledWith("qeos_SECRET");
  expect(await screen.findByText("Copied", { selector: "[role=status]" })).toBeInTheDocument();
});

test("a blocked clipboard says so instead of claiming success", async () => {
  setClipboard(vi.fn().mockRejectedValue(new Error("denied")));
  render(<SecretBlock label="Key ci" value="qeos_SECRET" copyLabel="Copy key ci" copyText="Copy key" />);
  await userEvent.click(screen.getByRole("button", { name: "Copy key ci" }));
  expect(await screen.findByText(/select the text and copy it/i, { selector: "[role=status]" })).toBeInTheDocument();
});

test("a new value resets the Copied state", async () => {
  setClipboard(vi.fn().mockResolvedValue(undefined));
  const { rerender } = render(<SecretBlock label="Key" value="one" copyLabel="Copy" copyText="Copy" />);
  await userEvent.click(screen.getByRole("button", { name: "Copy" }));
  await screen.findByText("Copied", { selector: "[role=status]" });
  rerender(<SecretBlock label="Key" value="two" copyLabel="Copy" copyText="Copy" />);
  expect(screen.getByRole("status")).toHaveTextContent("");
});
