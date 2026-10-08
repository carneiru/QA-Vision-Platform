import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import PageHeader from "./PageHeader";

test("renders the page name as the h1, with a muted subtitle", () => {
  render(<PageHeader title="Test cases" subtitle="1 083 cases" />, { wrapper: MemoryRouter });
  const h1 = screen.getByRole("heading", { level: 1, name: "Test cases" });
  // routeFocus moves focus here after a navigation
  expect(h1).toHaveAttribute("tabindex", "-1");
  expect(screen.getByText("1 083 cases")).toHaveClass("page-subtitle");
});

test("actions sit in their own group beside the title", () => {
  render(
    <PageHeader title="Runs" actions={<button className="primary">New run</button>} />,
    { wrapper: MemoryRouter },
  );
  const actions = screen.getByRole("button", { name: "New run" }).closest(".page-header-actions");
  expect(actions).not.toBeNull();
});

test("no subtitle, actions or tabs: only the heading", () => {
  const { container } = render(<PageHeader title="Flaky" />, { wrapper: MemoryRouter });
  expect(container.querySelector(".page-subtitle")).toBeNull();
  expect(container.querySelector(".page-header-actions")).toBeNull();
  expect(container.querySelector(".view-tabs")).toBeNull();
});

test("view tabs: the current one is marked, the others are links", () => {
  render(
    <PageHeader title="Test cases" tabs={[{ label: "Cases" }, { label: "Suites", to: "../suites" }]} />,
    { wrapper: MemoryRouter },
  );
  const tabs = screen.getByRole("navigation", { name: "Test cases views" });
  expect(within(tabs).getByText("Cases")).toHaveAttribute("aria-current", "page");
  expect(within(tabs).getByRole("link", { name: "Suites" })).toBeInTheDocument();
});
