import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import FilterSelect, { FilterOption } from "./FilterSelect";

const opts = (n: number): FilterOption[] =>
  Array.from({ length: n }, (_, i) => ({ value: `v${i}`, label: i === 3 ? "Ação três" : `Option ${i}` }));

function Harness({ n, onSubmit = () => {} }: { n: number; onSubmit?: () => void }) {
  const [value, setValue] = useState("");
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <FilterSelect label="Feature" value={value} options={opts(n)} onChange={setValue} />
      <output data-testid="value">{value}</output>
    </form>
  );
}

test("15 options render a native select", () => {
  render(<Harness n={15} />);
  expect(screen.getByRole("combobox", { name: "Feature" }).tagName).toBe("SELECT");
});

test("16 options render a searchable list with a count", async () => {
  const user = userEvent.setup();
  render(<Harness n={16} />);
  await user.click(screen.getByRole("button", { name: /feature/i }));
  const search = screen.getByRole("combobox", { name: /search feature/i });
  expect(search).toHaveFocus();
  expect(screen.getByText("16 of 16")).toBeInTheDocument();
  await user.type(search, "acao");
  expect(screen.getAllByRole("option")).toHaveLength(1);
  expect(screen.getByText("1 of 16")).toBeInTheDocument();
  await user.clear(search);
  await user.type(search, "zzz");
  expect(screen.getByText("No matches")).toBeInTheDocument();
});

test("keyboard picks an option and Escape returns focus to the trigger", async () => {
  const user = userEvent.setup();
  render(<Harness n={20} />);
  const trigger = screen.getByRole("button", { name: /feature/i });
  await user.click(trigger);
  await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
  expect(screen.getByTestId("value")).toHaveTextContent("v1");
  await user.click(trigger);
  await user.keyboard("{End}{Enter}");
  expect(screen.getByTestId("value")).toHaveTextContent("v19");
  await user.click(trigger);
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

test("enter in the search field picks and does not submit the form", async () => {
  const user = userEvent.setup();
  const submitted = vi.fn();
  render(<Harness n={20} onSubmit={submitted} />);
  await user.click(screen.getByRole("button", { name: /feature/i }));
  await user.keyboard("{ArrowDown}{Enter}");
  expect(submitted).not.toHaveBeenCalled();
  expect(screen.getByTestId("value")).toHaveTextContent("v0");
});

test("the selected value can be cleared", async () => {
  const user = userEvent.setup();
  render(<Harness n={20} />);
  await user.click(screen.getByRole("button", { name: /feature/i }));
  await user.click(screen.getByRole("option", { name: "Option 5" }));
  expect(screen.getByRole("button", { name: /^feature/i })).toHaveTextContent("Option 5");
  await user.click(screen.getByRole("button", { name: /clear feature/i }));
  expect(screen.getByTestId("value")).toHaveTextContent("");
});

test("closing by clicking outside forgets the search", async () => {
  const user = userEvent.setup();
  render(<Harness n={20} />);
  await user.click(screen.getByRole("button", { name: /feature/i }));
  await user.type(screen.getByRole("combobox", { name: /search feature/i }), "zzz");
  await user.click(screen.getByTestId("value"));
  expect(screen.queryByRole("combobox", { name: /search feature/i })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /feature/i }));
  expect(screen.getByRole("combobox", { name: /search feature/i })).toHaveValue("");
  expect(screen.getByText("20 of 20")).toBeInTheDocument();
});
