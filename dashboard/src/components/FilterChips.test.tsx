import { useState } from "react";
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

/** FilterChips over local state, as a page drives it from the URL */
function Live({ initial }: { initial: Record<string, string> }) {
  const [values, setValues] = useState(initial);
  const names: Record<string, string> = { status: "Status", label: "Label", q: "Search" };
  const applied = Object.entries(values).filter(([, v]) => v).map(([key, value]) => ({ key, name: names[key], value }));
  return (
    <>
      <button type="button">before</button>
      <FilterChips quick={QUICK} values={values} applied={applied}
        onChange={(patch) => setValues((v) => ({ ...v, ...patch }))}
        onClearAll={() => setValues({})} />
    </>
  );
}

test("removing a chip moves focus to the next chip", async () => {
  render(<Live initial={{ label: "flights", q: "legroom" }} />);
  await userEvent.click(screen.getByRole("button", { name: "Remove filter Label: flights" }));
  expect(screen.getByRole("button", { name: "Remove filter Search: legroom" })).toHaveFocus();
});

test("removing the last chip moves focus to the previous chip", async () => {
  render(<Live initial={{ label: "flights", q: "legroom" }} />);
  await userEvent.click(screen.getByRole("button", { name: "Remove filter Search: legroom" }));
  expect(screen.getByRole("button", { name: "Remove filter Label: flights" })).toHaveFocus();
});

test("Clear all moves focus to the chip group, never the page body", async () => {
  render(<Live initial={{ status: "ready", label: "flights" }} />);
  await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
  expect(screen.getByRole("group", { name: "Quick filters" })).toHaveFocus();
  expect(document.body).not.toHaveFocus();
});

test("with no quick chips, removing the only chip still leaves focus in the row", async () => {
  function NoQuick() {
    const [q, setQ] = useState("legroom");
    return (
      <FilterChips values={{ q }} applied={q ? [{ key: "q", name: "Search", value: q }] : []}
        onChange={(patch) => setQ(patch.q ?? q)} onClearAll={() => setQ("")} />
    );
  }
  render(<NoQuick />);
  await userEvent.click(screen.getByRole("button", { name: "Remove filter Search: legroom" }));
  expect(screen.getByRole("group", { name: "Quick filters" })).toHaveFocus();
});
