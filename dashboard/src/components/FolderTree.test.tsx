import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FolderTree, { buildTree } from "./FolderTree";

const folders = [
  { path: "tests", count: 6 }, { path: "tests/features", count: 6 },
  { path: "tests/features/hotels", count: 4 }, { path: "tests/features/hotels/booking", count: 3 },
  { path: "tests/features/flights", count: 2 },
];

test("leading single-child folders collapse", () => {
  const tree = buildTree(folders);
  expect(tree).toHaveLength(1);
  expect(tree[0]).toMatchObject({ path: "tests/features", name: "features", count: 6 });
  expect(tree[0].children.map((c) => c.name)).toEqual(["flights", "hotels"]);
});

test("nodes show counts and clicking selects, clicking again clears", async () => {
  const user = userEvent.setup();
  const onSelect = vi.fn();
  const { rerender } = render(<FolderTree folders={folders} total={7} selected="" onSelect={onSelect} />);
  expect(screen.getByRole("treeitem", { name: /all cases 7/i })).toBeInTheDocument();
  await user.click(screen.getByRole("treeitem", { name: /features 6/i }));
  expect(onSelect).toHaveBeenLastCalledWith("tests/features");
  rerender(<FolderTree folders={folders} total={7} selected="tests/features" onSelect={onSelect} />);
  await user.click(screen.getByRole("treeitem", { name: /features 6/i }));
  expect(onSelect).toHaveBeenLastCalledWith("");
});

test("keyboard: arrows move, right expands, left collapses, enter selects", async () => {
  const user = userEvent.setup();
  const onSelect = vi.fn();
  render(<FolderTree folders={folders} total={7} selected="" onSelect={onSelect} />);
  screen.getByRole("treeitem", { name: /all cases/i }).focus();
  await user.keyboard("{ArrowDown}");
  await user.keyboard("{ArrowRight}");
  expect(screen.getByRole("treeitem", { name: /hotels 4/i })).toBeInTheDocument();
  await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
  expect(onSelect).toHaveBeenLastCalledWith("tests/features/hotels");
  await user.keyboard("{ArrowLeft}");
  await user.keyboard("{ArrowLeft}");
  expect(screen.queryByRole("treeitem", { name: /hotels 4/i })).not.toBeInTheDocument();
});

test("the path to the selected folder starts expanded", () => {
  render(<FolderTree folders={folders} total={7} selected="tests/features/hotels/booking" onSelect={() => {}} />);
  expect(screen.getByRole("treeitem", { name: /booking 3/i })).toHaveAttribute("aria-selected", "true");
});

test("exactly one item is tabbable: the selected one, else All cases", () => {
  const { rerender } = render(<FolderTree folders={folders} total={7} selected="" onSelect={() => {}} />);
  expect(document.querySelectorAll('[role="treeitem"][tabindex="0"]')).toHaveLength(1);
  expect(screen.getByRole("treeitem", { name: /all cases/i })).toHaveAttribute("tabindex", "0");
  rerender(<FolderTree folders={folders} total={7} selected="tests/features" onSelect={() => {}} />);
  expect(screen.getByRole("treeitem", { name: /features 6/i })).toHaveAttribute("tabindex", "0");
});
