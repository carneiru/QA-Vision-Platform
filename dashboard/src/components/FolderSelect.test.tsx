import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FolderSelect from "./FolderSelect";

const folders = [
  { path: "tests", count: 6 }, { path: "tests/features", count: 6 },
  { path: "tests/features/hotels", count: 4 }, { path: "tests/features/hotels/booking", count: 3 },
  { path: "tests/features/flights", count: 2 },
];

const setup = (value = "", onChange = vi.fn()) => {
  render(<FolderSelect folders={folders} total={7} value={value} onChange={onChange} />);
  return { onChange, trigger: screen.getByRole("button", { name: /^folder/i }) };
};

test("closed it shows All folders, or the chosen folder from the collapsed root, with a clear button", async () => {
  const user = userEvent.setup();
  const { onChange } = setup("tests/features/hotels");
  expect(screen.getByRole("button", { name: /^folder/i })).toHaveTextContent("features / hotels");
  await user.click(screen.getByRole("button", { name: "Clear Folder" }));
  expect(onChange).toHaveBeenCalledWith("");
});

test("without a value there is no clear button", () => {
  setup();
  expect(screen.getByRole("button", { name: /^folder/i })).toHaveTextContent("All folders");
  expect(screen.queryByRole("button", { name: "Clear Folder" })).not.toBeInTheDocument();
});

test("opening shows the tree with counts and a focused search box", async () => {
  const user = userEvent.setup();
  const { trigger } = setup();
  await user.click(trigger);
  expect(screen.getByRole("searchbox", { name: "Search folders" })).toHaveFocus();
  expect(screen.getByRole("treeitem", { name: /all cases 7/i })).toBeInTheDocument();
  expect(screen.getByRole("treeitem", { name: /features 6/i })).toBeInTheDocument();
});

test("searching keeps the matches' ancestors and hides unrelated folders", async () => {
  const user = userEvent.setup();
  const { trigger } = setup();
  await user.click(trigger);
  await user.type(screen.getByRole("searchbox", { name: "Search folders" }), "BOOKING");
  expect(screen.getByRole("treeitem", { name: /booking 3/i })).toBeInTheDocument();
  expect(screen.getByRole("treeitem", { name: /hotels 4/i })).toBeInTheDocument();
  expect(screen.getByRole("treeitem", { name: /features 6/i })).toBeInTheDocument();
  expect(screen.queryByRole("treeitem", { name: /flights/i })).not.toBeInTheDocument();
  expect(screen.getByText("booking", { selector: "mark" })).toBeInTheDocument();
});

test("a search with no match says so", async () => {
  const user = userEvent.setup();
  const { trigger } = setup();
  await user.click(trigger);
  await user.type(screen.getByRole("searchbox", { name: "Search folders" }), "zzz");
  expect(screen.getByText("No matches")).toBeInTheDocument();
  expect(screen.queryByRole("tree")).not.toBeInTheDocument();
});

test("picking a folder calls onChange, closes and returns focus to the trigger", async () => {
  const user = userEvent.setup();
  const { trigger, onChange } = setup();
  await user.click(trigger);
  await user.click(screen.getByRole("treeitem", { name: /features 6/i }));
  expect(onChange).toHaveBeenLastCalledWith("tests/features");
  expect(screen.queryByRole("tree")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

test("picking All cases chooses no folder", async () => {
  const user = userEvent.setup();
  const { trigger, onChange } = setup("tests/features");
  await user.click(trigger);
  await user.click(screen.getByRole("treeitem", { name: /all cases/i }));
  expect(onChange).toHaveBeenLastCalledWith("");
});

test("clicking the chosen folder keeps it", async () => {
  const user = userEvent.setup();
  const { trigger, onChange } = setup("tests/features");
  await user.click(trigger);
  await user.click(screen.getByRole("treeitem", { name: /features 6/i }));
  expect(onChange).toHaveBeenLastCalledWith("tests/features");
});

test("Escape closes and returns focus; an outside click closes and resets the search", async () => {
  const user = userEvent.setup();
  const { trigger } = setup();
  await user.click(trigger);
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("tree")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  await user.click(trigger);
  await user.type(screen.getByRole("searchbox", { name: "Search folders" }), "hotels");
  await user.click(document.body);
  expect(screen.queryByRole("tree")).not.toBeInTheDocument();
  await user.click(trigger);
  expect(screen.getByRole("searchbox", { name: "Search folders" })).toHaveValue("");
});

test("keyboard: down from the search enters the tree, Enter picks, up from the first item returns", async () => {
  const user = userEvent.setup();
  const { trigger, onChange } = setup();
  await user.click(trigger);
  await user.keyboard("{ArrowDown}");
  expect(screen.getByRole("treeitem", { name: /all cases/i })).toHaveFocus();
  await user.keyboard("{ArrowUp}");
  expect(screen.getByRole("searchbox", { name: "Search folders" })).toHaveFocus();
  await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
  expect(onChange).toHaveBeenLastCalledWith("tests/features");
  expect(trigger).toHaveFocus();
});
