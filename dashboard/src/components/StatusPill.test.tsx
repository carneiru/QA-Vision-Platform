import { render, screen } from "@testing-library/react";
import StatusPill, { CaseStatusPill } from "./StatusPill";

test.each([
  ["passed", "Passed"],
  ["failed", "Failed"],
  ["errored", "Errored"],
  ["running", "Running"],
] as const)("a %s pill shows the word, a tone class and an icon", (tone, word) => {
  const { container } = render(<StatusPill tone={tone} label={word} />);
  const pill = screen.getByText(word).closest(".pill")!;
  expect(pill).toHaveClass("pill", `pill-${tone}`);
  // The colour is never alone: an icon (hidden from assistive tech) sits beside the word
  expect(container.querySelector(".pill svg")).toHaveAttribute("aria-hidden", "true");
});

test("a neutral pill has no status colour and no icon", () => {
  const { container } = render(<StatusPill tone="neutral" label="Draft" />);
  expect(screen.getByText("Draft").closest(".pill")).toHaveClass("pill-neutral");
  expect(container.querySelector(".pill svg")).toBeNull();
});

test.each([
  ["draft", "Draft", "pill-neutral"],
  ["ready", "Ready", "pill-ready"],
  ["archived", "Archived", "pill-neutral"],
])("case status %s reads %s", (status, word, cls) => {
  render(<CaseStatusPill status={status} />);
  expect(screen.getByText(word).closest(".pill")).toHaveClass(cls);
});

test("a note extends the word", () => {
  render(<StatusPill tone="passed" label="Passed" note="2 quarantined" />);
  expect(screen.getByText("Passed · 2 quarantined")).toBeInTheDocument();
});
