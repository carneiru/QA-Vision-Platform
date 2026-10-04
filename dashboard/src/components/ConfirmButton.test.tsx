import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConfirmButton from "./ConfirmButton";

function setup() {
  const onConfirm = vi.fn();
  render(
    <ConfirmButton
      label="Revoke"
      ariaLabel="Revoke key ci"
      question="Revoke key ci? Uploads using it stop working immediately."
      confirmLabel="Revoke"
      onConfirm={onConfirm}
    />,
  );
  return onConfirm;
}

test("the first click only asks; the confirm button takes focus", async () => {
  const onConfirm = setup();
  await userEvent.click(screen.getByRole("button", { name: "Revoke key ci" }));
  expect(onConfirm).not.toHaveBeenCalled();
  expect(screen.getByText(/uploads using it stop working/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Revoke" })).toHaveFocus();
});

test("confirming runs the action once", async () => {
  const onConfirm = setup();
  await userEvent.click(screen.getByRole("button", { name: "Revoke key ci" }));
  await userEvent.click(screen.getByRole("button", { name: "Revoke" }));
  expect(onConfirm).toHaveBeenCalledTimes(1);
});

test("cancel and Escape back out and return focus to the trigger", async () => {
  const onConfirm = setup();
  await userEvent.click(screen.getByRole("button", { name: "Revoke key ci" }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("button", { name: "Revoke key ci" })).toHaveFocus();

  await userEvent.click(screen.getByRole("button", { name: "Revoke key ci" }));
  await userEvent.keyboard("{Escape}");
  expect(screen.getByRole("button", { name: "Revoke key ci" })).toHaveFocus();
  expect(onConfirm).not.toHaveBeenCalled();
});
