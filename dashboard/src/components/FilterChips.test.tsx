import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import FilterChips, { type AppliedFilter, type QuickChip } from "./FilterChips";

const QUICK: QuickChip[] = [
  { key: "status", value: "draft", label: "Draft" },
  { key: "status", value: "ready", label: "Ready" },
  { key: "linked", value: "true", label: "Linked" },
];

function setup(values: Record<string, string>, applied: AppliedFilter[] = [], onAddFilter?: () => void) {
  const onChange = vi.fn();
  const onClearAll = vi.fn();
  render(<FilterChips quick={QUICK} values={values} applied={applied} onChange={onChange} onClearAll={onClearAll} onAddFilter={onAddFilter} />);
  return { onChange, onClearAll };
}

test("quick chips are toggle buttons whose pressed state follows the values", () => {
  setup({ status: "ready", linked: "" });
  expect(screen.getByRole("button", { name: "Ready" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "Draft" })).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByRole("button", { name: "Linked" })).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByRole("button", { name: "Ready" })).toHaveClass("fchip", "is-on");
});

test("pressing an off chip sets its value; pressing the on chip clears it", async () => {
  const { onChange } = setup({ status: "ready", linked: "" });
  await userEvent.click(screen.getByRole("button", { name: "Linked" }));
  expect(onChange).toHaveBeenLastCalledWith({ linked: "true" });
  await userEvent.click(screen.getByRole("button", { name: "Ready" }));
  expect(onChange).toHaveBeenLastCalledWith({ status: "" });
});

test("chips for the same key are one choice: pressing Draft while Ready is on switches the value", async () => {
  const { onChange } = setup({ status: "ready" });
  await userEvent.click(screen.getByRole("button", { name: "Draft" }));
  expect(onChange).toHaveBeenLastCalledWith({ status: "draft" });
});

test("Space and Enter toggle a chip from the keyboard", async () => {
  const { onChange } = setup({ status: "" });
  await userEvent.tab();
  expect(screen.getByRole("button", { name: "Draft" })).toHaveFocus();
  await userEvent.keyboard(" ");
  expect(onChange).toHaveBeenLastCalledWith({ status: "draft" });
  await userEvent.tab();
  await userEvent.keyboard("{Enter}");
  expect(onChange).toHaveBeenLastCalledWith({ status: "ready" });
});

test("applied filters that are not quick chips are removable chips with a named remove button", async () => {
  const { onChange } = setup({ status: "ready" }, [
    { key: "status", name: "Status", value: "Ready" },
    { key: "label", name: "Label", value: "flights" },
    { key: "folder", name: "Folder", value: "features / hotels" },
  ]);
  // Ready is shown by its quick chip, not a second time
  expect(screen.queryByRole("button", { name: "Remove filter Status: Ready" })).not.toBeInTheDocument();
  expect(screen.getByText("Label: flights")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Remove filter Folder: features / hotels" }));
  expect(onChange).toHaveBeenLastCalledWith({ folder: "" });
});

test("an applied value with no quick chip of its own shows as removable even when its key has quick chips", () => {
  setup({ status: "archived" }, [{ key: "status", name: "Status", value: "Archived" }]);
  expect(screen.getByRole("button", { name: "Remove filter Status: Archived" })).toBeInTheDocument();
});

test("no Clear all while nothing is applied", () => {
  setup({ status: "" });
  expect(screen.getByRole("group", { name: "Quick filters" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Clear all" })).not.toBeInTheDocument();
});

test("Clear all clears every filter, quick or not", async () => {
  const { onClearAll } = setup({ linked: "true" }, [{ key: "label", name: "Label", value: "flights" }]);
  await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
  expect(onClearAll).toHaveBeenCalledTimes(1);
});

test("+ Filter is shown when the page has more filters, and calls back", async () => {
  const onAdd = vi.fn();
  setup({}, [], onAdd);
  const group = screen.getByRole("group", { name: "Quick filters" });
  await userEvent.click(within(group).getByRole("button", { name: "+ Filter" }));
  expect(onAdd).toHaveBeenCalledTimes(1);
});

test("no + Filter without a disclosure to open", () => {
  setup({});
  expect(screen.queryByRole("button", { name: "+ Filter" })).not.toBeInTheDocument();
});
