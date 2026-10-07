import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { oneOf, useDraft, useUrlState } from "./useUrlState";

const DEFAULTS = { days: "30", q: "" } as const;

function Probe() {
  const { values, offset, update, setOffset } = useUrlState(DEFAULTS, 50);
  const { search } = useLocation();
  const navigate = useNavigate();
  return (
    <div>
      <output aria-label="state">{JSON.stringify({ ...values, offset })}</output>
      <output aria-label="search">{search}</output>
      <button onClick={() => setOffset(offset + 50)}>next</button>
      <button onClick={() => update({ days: "7" })}>seven</button>
      <button onClick={() => update({ days: "30" })}>thirty</button>
      <button onClick={() => navigate(-1)}>back</button>
    </div>
  );
}

const renderAt = (url: string) => render(<MemoryRouter initialEntries={[url]}><Probe /></MemoryRouter>);
const state = () => JSON.parse(screen.getByLabelText("state").textContent!);

test("reads values and offset from the URL, defaults otherwise", () => {
  renderAt("/x?days=7&offset=100");
  expect(state()).toEqual({ days: "7", q: "", offset: 100 });
});

test("a junk offset reads as page 1", () => {
  renderAt("/x?offset=-5");
  expect(state().offset).toBe(0);
  renderAt("/x?offset=abc");
});

test("changing a filter resets the page and never writes defaults", async () => {
  renderAt("/x?offset=50");
  await userEvent.click(screen.getByText("seven"));
  expect(screen.getByLabelText("search").textContent).toBe("?days=7");
  await userEvent.click(screen.getByText("thirty"));
  expect(screen.getByLabelText("search").textContent).toBe("");
});

test("paging writes offset and keeps the filters", async () => {
  renderAt("/x?days=7");
  await userEvent.click(screen.getByText("next"));
  expect(screen.getByLabelText("search").textContent).toBe("?days=7&offset=50");
});

test("oneOf falls back for values outside the set", () => {
  expect(oneOf("7", ["7", "30"], "30")).toBe("7");
  expect(oneOf("x", ["7", "30"], "30")).toBe("30");
});

test("Back restores the previous filters", async () => {
  renderAt("/x?days=7");
  await userEvent.click(screen.getByText("next"));
  expect(state().offset).toBe(50);
  await userEvent.click(screen.getByText("back"));
  expect(state()).toEqual({ days: "7", q: "", offset: 0 });
});

function DraftProbe() {
  const { values, update } = useUrlState(DEFAULTS, 50);
  const [draft, setDraft, commit] = useDraft(values.q);
  return (
    <form onSubmit={(e) => { e.preventDefault(); update({ q: commit((s) => s.trim()) }); }}>
      <input aria-label="q" value={draft} onChange={(e) => setDraft(e.target.value)} />
      <button>apply</button>
    </form>
  );
}

test("a draft is rewritten to its normalized form on submit, even when the URL value does not change", async () => {
  render(<MemoryRouter initialEntries={["/x?q=abc"]}><DraftProbe /></MemoryRouter>);
  const input = screen.getByLabelText("q");
  await userEvent.clear(input);
  await userEvent.type(input, "  abc  ");
  expect(input).toHaveValue("  abc  ");
  await userEvent.click(screen.getByText("apply"));
  expect(input).toHaveValue("abc"); // the URL value stayed "abc": only the draft needed resyncing
});

test("a typed draft is left alone when another filter changes", async () => {
  render(<MemoryRouter initialEntries={["/x?q=one"]}><DraftProbe /><Probe /></MemoryRouter>);
  const input = screen.getByLabelText("q");
  await userEvent.type(input, "!");
  expect(input).toHaveValue("one!");
  await userEvent.click(screen.getByText("seven")); // a filter change elsewhere leaves a typed draft alone
  expect(input).toHaveValue("one!");
});
