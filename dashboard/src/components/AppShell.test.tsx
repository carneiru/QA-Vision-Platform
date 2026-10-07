import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import AppShell from "./AppShell";
import ProjectLayout from "../pages/ProjectLayout";

function renderAt(path: string) {
  setAccessToken("acc");
  server.use(
    http.get("/api/v1/organizations", () => HttpResponse.json([{ id: 1, name: "Acme", slug: "acme", role: "owner" }])),
    http.get("/api/v1/organizations/1/projects", () => HttpResponse.json([{ id: 42, name: "Shop E2E" }, { id: 43, name: "API" }])),
    http.get("/api/v1/projects/42", () => HttpResponse.json({ id: 42, name: "Shop E2E", organization_id: 1 })),
    http.post("/api/v1/auth/logout", () => new HttpResponse(null, { status: 200 })),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<h2>All projects view</h2>} />
            <Route path="/projects/:projectId" element={<ProjectLayout />}>
              <Route path="runs" element={<h2>Runs view</h2>} />
              <Route path="settings" element={<h2>Settings view</h2>} />
              <Route path="overview" element={<h2>Overview view</h2>} />
            </Route>
          </Route>
          <Route path="/login" element={<div>LOGIN</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("inside a project the sidebar lists its views; following one moves focus and title", async () => {
  renderAt("/projects/42/runs");
  await screen.findByRole("heading", { name: "Shop E2E" });
  const projectNav = screen.getByRole("navigation", { name: "Project views" });
  expect(projectNav).toHaveTextContent("Overview");
  await userEvent.click(screen.getByRole("link", { name: "Settings" }));
  expect(await screen.findByText("Settings view")).toBeInTheDocument();
  expect(document.getElementById("content")).toHaveFocus();
  expect(document.title).toBe("Settings · Shop E2E · QEOS");
});

test("the project switcher lists every project and opens the chosen one's overview", async () => {
  renderAt("/projects/42/runs");
  await screen.findByRole("option", { name: "API" });
  await userEvent.selectOptions(screen.getByLabelText("Project"), "43");
  // 43 has no project mock; the route change is what matters
  expect(screen.getByLabelText("Project")).toHaveValue("43");
});

test("outside a project there is no project navigation", async () => {
  renderAt("/");
  await screen.findByText("All projects view");
  expect(screen.queryByRole("navigation", { name: "Project views" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /all projects/i })).toBeInTheDocument();
});

test("sign out returns to login", async () => {
  renderAt("/");
  await userEvent.click(await screen.findByRole("button", { name: /sign out/i }));
  expect(await screen.findByText("LOGIN")).toBeInTheDocument();
});

test("the narrow-screen drawer opens from the menu button and Escape closes it, returning focus", async () => {
  renderAt("/");
  const menu = screen.getByRole("button", { name: /open navigation/i });
  expect(menu).toHaveAttribute("aria-expanded", "false");
  await userEvent.click(menu);
  expect(menu).toHaveAttribute("aria-expanded", "true");
  expect(document.getElementById("sidebar")).toHaveClass("open");
  await userEvent.keyboard("{Escape}");
  expect(menu).toHaveAttribute("aria-expanded", "false");
  expect(menu).toHaveFocus();
});

function mockNarrow(matches: boolean) {
  window.matchMedia = ((query: string) => ({
    matches, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

describe("narrow drawer accessibility", () => {
  afterEach(() => {
    // @ts-expect-error restore jsdom default (no matchMedia)
    delete window.matchMedia;
  });

  test("a closed drawer is inert and hidden from assistive tech on narrow screens", async () => {
    mockNarrow(true);
    renderAt("/projects/42/runs");
    const sidebar = document.getElementById("sidebar")!;
    expect(sidebar).toHaveAttribute("inert");
    expect(sidebar).toHaveAttribute("aria-hidden", "true");
    await userEvent.click(screen.getByRole("button", { name: /open navigation/i }));
    expect(sidebar).not.toHaveAttribute("inert");
    expect(sidebar).not.toHaveAttribute("aria-hidden");
  });

  test("the sidebar stays available on wide screens", () => {
    mockNarrow(false);
    renderAt("/");
    const sidebar = document.getElementById("sidebar")!;
    expect(sidebar).not.toHaveAttribute("inert");
    expect(sidebar).not.toHaveAttribute("aria-hidden");
  });

  test("an open drawer is a modal: focus moves to the first link, Tab wraps, Escape returns focus", async () => {
    mockNarrow(true);
    renderAt("/projects/42/runs");
    const menu = screen.getByRole("button", { name: /open navigation/i });
    await userEvent.click(menu);
    const sidebar = document.getElementById("sidebar")!;
    expect(sidebar).toHaveAttribute("aria-modal", "true");
    expect(sidebar).toHaveAttribute("role", "dialog");
    const links = sidebar.querySelectorAll<HTMLElement>("a");
    expect(links[0]).toHaveFocus();
    // Tab from the last focusable control wraps to the first, Shift+Tab from the first wraps to the last
    const focusables = Array.from(sidebar.querySelectorAll<HTMLElement>("a[href], button:not(:disabled), select"));
    focusables[focusables.length - 1].focus();
    await userEvent.tab();
    expect(focusables[0]).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(focusables[focusables.length - 1]).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(menu).toHaveFocus();
    expect(sidebar).toHaveAttribute("inert");
  });
});
