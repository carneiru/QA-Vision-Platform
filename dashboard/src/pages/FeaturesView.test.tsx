import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import CasesPage from "./CasesPage";

const P = "/api/v1/projects/42";
const KEY = "c".repeat(64);
const TARGET = { available: true, configured: true, provider: "github", repo: "acme/obt", workflow: "qeos-run.yml",
  ref: "main", token_last4: "a1b2", token_expires_at: null, updated_at: "2026-10-07T10:00:00Z", last_change: null };

const kase = (number: number, extra: object = {}) => ({
  number, key: `TC-${number}`, title: `Case ${number}`, description: null, steps: [], labels: [], priority: "medium",
  status: "draft", automated_test_key: null, automated_name: null, created_by: 1, created_at: "2026-10-06T10:00:00Z",
  updated_by: null, updated_at: null, suites: [], source_path: null, gherkin: null, feature_name: null, ...extra,
});

const LOGIN = { feature_name: "Login", path: "features/auth/login.feature", folder: "features/auth", case_count: 2,
  case_numbers: [1, 2], has_source: true };
const MANUAL = { feature_name: null, path: null, folder: null, case_count: 1, case_numbers: [9], has_source: false };

const detailCase = (number: number, extra: object = {}) => ({
  number, key: `TC-${number}`, title: `Case ${number}`, scenario_name: `Case ${number}`, status: "ready",
  priority: "high", automated_test_key: null, line: null, ...extra,
});
const LOGIN_DETAIL = {
  feature_name: "Login", path: LOGIN.path, folder: LOGIN.folder, content: null, imported_at: null,
  // File order; case 3 no longer matches the filters, so the row's case_numbers leave it out
  cases: [detailCase(2, { automated_test_key: KEY }), detailCase(3), detailCase(1)],
};

function Location() {
  const { pathname, search } = useLocation();
  return <output data-testid="where">{pathname + search}</output>;
}

const seenFeatures: URLSearchParams[] = [];
const seenCases: URLSearchParams[] = [];

beforeEach(() => {
  seenFeatures.length = 0;
  seenCases.length = 0;
  server.use(
    http.get(P, () => HttpResponse.json({ id: 42, organization_id: 1, name: "Web", my_role: "member" })),
    http.get(`${P}/ci-target`, () => HttpResponse.json(TARGET)),
    http.get(`${P}/case-features`, () => HttpResponse.json([])),
    http.get(`${P}/case-folders`, () => HttpResponse.json([])),
    http.get(`${P}/case-labels`, () => HttpResponse.json([])),
    http.get(`${P}/cases`, ({ request }) => {
      const sp = new URL(request.url).searchParams;
      if (sp.get("limit") !== "1") seenCases.push(sp);
      if (sp.get("origin") === "manual") return HttpResponse.json({ total: 1, items: [kase(9, { title: "Written by hand" })] });
      return HttpResponse.json({ total: 2, items: [kase(1), kase(2)] });
    }),
    http.get(`${P}/features`, ({ request }) => {
      seenFeatures.push(new URL(request.url).searchParams);
      return HttpResponse.json({ total: 2, items: [LOGIN, MANUAL] });
    }),
    http.get(`${P}/features/detail`, () => HttpResponse.json(LOGIN_DETAIL)),
    http.post(`${P}/analytics/run-strip`, () => HttpResponse.json({ runs: [], statuses: {} })),
  );
});

function renderCases(url = "/projects/42/cases") {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <Routes><Route path="/projects/:projectId/cases" element={<><CasesPage /><Location /></>} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const featureRow = (name: string) => screen.getByText(name, { selector: "a, .feature-name" }).closest("tr")!;

test("the Cases list opens grouped by feature: one row per .feature file, manual cases last", async () => {
  renderCases();
  const link = await screen.findByRole("link", { name: "Login" });
  expect(link).toHaveAttribute("href", "/projects/42/cases/feature?path=features%2Fauth%2Flogin.feature");
  const row = link.closest("tr")!;
  expect(within(row).getByText("features/auth")).toBeInTheDocument();
  expect(within(row).getByRole("cell", { name: "2" })).toHaveClass("num");
  expect(screen.getByText("No feature (manual)")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "No feature (manual)" })).not.toBeInTheDocument();
  // Feature view searches in feature names and paths unless told otherwise, and the server is always told
  expect(seenFeatures[0].get("search_in")).toBe("feature");
  expect(seenFeatures[0].get("limit")).toBe("50");
});

test("Group by is a pressed-button group stored in the URL; Scenario shows today's list", async () => {
  renderCases();
  await screen.findByRole("link", { name: "Login" });
  const group = screen.getByRole("group", { name: "Group by" });
  expect(within(group).getByRole("button", { name: "Feature" })).toHaveAttribute("aria-pressed", "true");
  expect(within(group).getByRole("button", { name: "Scenario" })).toHaveAttribute("aria-pressed", "false");
  await userEvent.click(within(group).getByRole("button", { name: "Scenario" }));
  expect(await screen.findByRole("link", { name: "Case 1" })).toBeInTheDocument();
  expect(screen.getByTestId("where")).toHaveTextContent("group=scenario");
  expect(within(group).getByRole("button", { name: "Scenario" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.queryByRole("link", { name: "Login" })).not.toBeInTheDocument();
});

test("Search in defaults to Feature in Feature view and Scenario in Scenario view, and reaches the API", async () => {
  renderCases();
  await screen.findByRole("link", { name: "Login" });
  expect(screen.getByRole("combobox", { name: "Search in" })).toHaveValue("feature");
  await userEvent.type(screen.getByLabelText("Search"), "pay");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Search in" }), "both");
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  await waitFor(() => expect(seenFeatures[seenFeatures.length - 1].get("search_in")).toBe("both"));
  expect(seenFeatures[seenFeatures.length - 1].get("search")).toBe("pay");
  expect(screen.getByTestId("where")).toHaveTextContent("search_in=both");
});

test("Scenario view searches scenarios by default and sends search_in to /cases", async () => {
  renderCases("/projects/42/cases?group=scenario&q=login");
  await screen.findByRole("link", { name: "Case 1" });
  expect(screen.getByRole("combobox", { name: "Search in" })).toHaveValue("scenario");
  expect(seenCases[seenCases.length - 1].get("search_in")).toBe("scenario");
});

test("Apply keeps the grouping", async () => {
  renderCases("/projects/42/cases?group=scenario");
  await screen.findByRole("link", { name: "Case 1" });
  await userEvent.type(screen.getByLabelText("Search"), "x");
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("q=x"));
  expect(screen.getByTestId("where")).toHaveTextContent("group=scenario");
});

test("a feature row expands in place to its matching scenarios, in file order", async () => {
  renderCases();
  await screen.findByRole("link", { name: "Login" });
  const toggle = within(featureRow("Login")).getByRole("button", { name: "Show scenarios of Login" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  await userEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  const scenarios = await screen.findByRole("rowgroup", { name: "Scenarios of Login" });
  const titles = within(scenarios).getAllByRole("link").filter((a) => a.classList.contains("case-title")).map((a) => a.textContent);
  expect(titles).toEqual(["Case 2", "Case 1"]);
  expect(within(scenarios).getByRole("link", { name: "Case 2" })).toHaveAttribute("href", "/projects/42/cases/2");
  await userEvent.click(toggle);
  expect(screen.queryByRole("rowgroup", { name: "Scenarios of Login" })).not.toBeInTheDocument();
});

test("feature and scenario rows share one table: the Scenario view's columns plus Scenarios, filled on feature rows only", async () => {
  renderCases();
  await screen.findByRole("link", { name: "Login" });
  await userEvent.click(within(featureRow("Login")).getByRole("button", { name: "Show scenarios of Login" }));
  const scenarios = await screen.findByRole("rowgroup", { name: "Scenarios of Login" });
  expect(screen.getAllByRole("table")).toHaveLength(1);
  const heads = within(screen.getByRole("table")).getAllByRole("columnheader").map((th) => th.textContent);
  expect(heads).toEqual(["Select", "Title", "Scenarios", "Last runs", "Priority", "Status", "Automated"]);
  const caseRow = within(scenarios).getByRole("link", { name: "Case 2" }).closest("tr")!;
  const cells = within(caseRow).getAllByRole("cell");
  expect(cells).toHaveLength(heads.length);
  expect(cells[2]).toHaveTextContent("");
  expect(cells[4]).toHaveTextContent("high");
  expect(cells[6]).toHaveTextContent("Linked");
  expect(within(featureRow("Login")).getAllByRole("cell")).toHaveLength(heads.length);
});

test("the manual group expands to the manual cases", async () => {
  renderCases();
  await screen.findByText("No feature (manual)");
  await userEvent.click(within(featureRow("No feature (manual)")).getByRole("button", { name: "Show scenarios of No feature (manual)" }));
  expect(await screen.findByRole("link", { name: "Written by hand" })).toBeInTheDocument();
  expect(seenCases.some((sp) => sp.get("origin") === "manual")).toBe(true);
});

test("checking a feature selects its runnable scenarios; the box is tri-state", async () => {
  renderCases();
  await screen.findByRole("link", { name: "Login" });
  const box = within(featureRow("Login")).getByRole("checkbox", { name: "Select every scenario of Login" }) as HTMLInputElement;
  // A manual group has nothing to run, so no box
  expect(within(featureRow("No feature (manual)")).queryByRole("checkbox")).not.toBeInTheDocument();
  await userEvent.click(box);
  expect(await screen.findByRole("button", { name: "Run selected (2)" })).toBeInTheDocument();
  expect(box).toBeChecked();
  await userEvent.click(within(featureRow("Login")).getByRole("button", { name: "Show scenarios of Login" }));
  const scenarios = await screen.findByRole("rowgroup", { name: "Scenarios of Login" });
  await userEvent.click(within(scenarios).getByRole("checkbox", { name: "Select TC-1 Case 1" }));
  expect(screen.getByRole("button", { name: "Run selected (1)" })).toBeInTheDocument();
  expect(box).not.toBeChecked();
  expect(box.indeterminate).toBe(true);
  await userEvent.click(box);
  expect(await screen.findByRole("button", { name: "Run selected (2)" })).toBeInTheDocument();
  await userEvent.click(box);
  expect(screen.queryByRole("button", { name: /Run selected/ })).not.toBeInTheDocument();
});

test("a feature row counts its failing scenarios from the latest-result join", async () => {
  server.use(
    http.get(`${P}/analytics/latest-keys`, () => HttpResponse.json({ keys: [KEY] })),
    http.post(`${P}/cases/search`, () => HttpResponse.json({ total: 1, items: [kase(2, { automated_test_key: KEY })] })),
  );
  renderCases();
  await screen.findByRole("link", { name: "Login" });
  // The column on wide screens, and the narrow line under the name on phones
  expect(await within(featureRow("Login")).findAllByText("1 failing")).toHaveLength(2);
  expect(within(featureRow("No feature (manual)")).queryByText(/failing/)).not.toBeInTheDocument();
});

test("a filter the feature list cannot apply groups the matching cases in the page instead", async () => {
  server.use(http.get(`${P}/cases`, ({ request }) => {
    const sp = new URL(request.url).searchParams;
    if (sp.get("limit") !== "1") seenCases.push(sp);
    return HttpResponse.json({ total: 3, items: [
      kase(1, { source_path: LOGIN.path, feature_name: "Login" }),
      kase(4, { source_path: "features/pay.feature", feature_name: "Pay" }),
      kase(9, { title: "Written by hand" }),
    ] });
  }));
  renderCases("/projects/42/cases?origin=imported");
  expect(await screen.findByRole("link", { name: "Login" })).toBeInTheDocument();
  expect(within(featureRow("Login")).getByRole("cell", { name: "1" })).toHaveClass("num");
  expect(screen.getByRole("link", { name: "Pay" })).toBeInTheDocument();
  expect(seenFeatures).toHaveLength(0);
  expect(seenCases[seenCases.length - 1].get("origin")).toBe("imported");
  await userEvent.click(within(featureRow("Pay")).getByRole("button", { name: "Show scenarios of Pay" }));
  expect(await screen.findByRole("link", { name: "Case 4" })).toBeInTheDocument();
});

const withFeatures = (...items: object[]) =>
  server.use(http.get(`${P}/features`, () => HttpResponse.json({ total: items.length, items })));
const STATUSES = { draft: 0, ready: 0, archived: 0 };

test("a feature row shows its highest priority, its statuses and how many scenarios are linked", async () => {
  withFeatures({ ...LOGIN, case_count: 5, case_numbers: [1, 2, 3, 4, 5], linked_count: 3, top_priority: "high",
    status_counts: { ...STATUSES, ready: 2, draft: 1, archived: 2 } });
  renderCases();
  await screen.findByRole("link", { name: "Login" });
  const row = featureRow("Login");
  expect(within(row).getByLabelText("Highest priority: high")).toHaveTextContent("high");
  expect(within(row).getByText("2 ready · 1 draft · 2 archived")).toHaveClass("muted");
  expect(within(row).queryByText("ready", { selector: ".pill, .status-pill, span" })).not.toBeInTheDocument();
  expect(within(row).getAllByText("3 of 5 linked").length).toBeGreaterThan(0);
});

test("a feature whose scenarios share one status shows a single pill, and an all-linked one says so", async () => {
  withFeatures({ ...LOGIN, linked_count: 2, top_priority: "medium", status_counts: { ...STATUSES, ready: 2 } });
  renderCases();
  await screen.findByRole("link", { name: "Login" });
  const row = featureRow("Login");
  expect(within(row).getByText("Ready")).toBeInTheDocument();
  expect(within(row).queryByText(/·/)).not.toBeInTheDocument();
  const all = within(within(row).getAllByRole("cell").at(-1)!).getByText("All linked");
  expect(all).toHaveClass("linked");
});

test("a manual group says Manual and shows nothing for a missing priority", async () => {
  withFeatures({ ...MANUAL, linked_count: 0, top_priority: null, status_counts: { ...STATUSES, draft: 1 } });
  renderCases();
  await screen.findByText("No feature (manual)");
  const row = featureRow("No feature (manual)");
  expect(within(within(row).getAllByRole("cell").at(-1)!).getByText("Manual")).toHaveClass("muted");
  expect(within(row).queryByLabelText(/Highest priority/)).not.toBeInTheDocument();
  expect(within(row).getByText("Draft")).toBeInTheDocument();
});

test("an older server's feature row leaves the aggregate cells empty", async () => {
  renderCases();
  await screen.findByRole("link", { name: "Login" });
  const cells = within(featureRow("Login")).getAllByRole("cell").slice(-3);
  expect(cells.map((c) => c.textContent)).toEqual(["", "", ""]);
});

test("the client-side grouping computes the same aggregates from the cases", async () => {
  server.use(http.get(`${P}/cases`, () => HttpResponse.json({ total: 3, items: [
    kase(1, { source_path: LOGIN.path, feature_name: "Login", priority: "low", status: "ready", automated_test_key: KEY }),
    kase(2, { source_path: LOGIN.path, feature_name: "Login", priority: "critical", status: "draft" }),
    kase(3, { source_path: "features/pay.feature", feature_name: "Pay", status: "ready", automated_test_key: KEY }),
  ] })));
  renderCases("/projects/42/cases?origin=imported");
  await screen.findByRole("link", { name: "Login" });
  const login = featureRow("Login");
  expect(within(login).getByLabelText("Highest priority: critical")).toBeInTheDocument();
  expect(within(login).getByText("1 ready · 1 draft")).toBeInTheDocument();
  expect(within(login).getAllByText("1 of 2 linked").length).toBeGreaterThan(0);
  const pay = featureRow("Pay");
  expect(within(pay).getByText("Ready")).toBeInTheDocument();
  expect(within(pay).getAllByText("All linked").length).toBeGreaterThan(0);
});
