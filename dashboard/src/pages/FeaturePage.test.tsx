import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import FeaturePage from "./FeaturePage";

const P = "/api/v1/projects/42";
const KEY = "d".repeat(64);
const PATH = "features/auth/login.feature";
const URL_ = `/projects/42/cases/feature?path=${encodeURIComponent(PATH)}`;
const TARGET = { available: true, configured: true, provider: "github", repo: "acme/obt", workflow: "qeos-run.yml",
  ref: "main", token_last4: "a1b2", token_expires_at: null, updated_at: "2026-10-07T10:00:00Z", last_change: null };

const CONTENT = [
  "@auth",
  "Feature: Login",
  "",
  "  Scenario: Good password",
  '    Given I type "secret"',
  "",
  "  Scenario: Bad password",
  "    Then I see an error",
].join("\n");

const detailCase = (number: number, extra: object = {}) => ({
  number, key: `TC-${number}`, title: `Title ${number}`, scenario_name: `Scenario ${number}`, status: "ready",
  priority: "high", automated_test_key: null, line: null, ...extra,
});
const DETAIL = {
  feature_name: "Login", path: PATH, folder: "features/auth", content: CONTENT, imported_at: "2026-10-08T09:00:00Z",
  cases: [
    detailCase(12, { scenario_name: "Good password", line: 4, automated_test_key: KEY }),
    detailCase(13, { scenario_name: "Bad password", line: 7 }),
  ],
};

const kase = (number: number, extra: object = {}) => ({
  number, key: `TC-${number}`, title: `Title ${number}`, description: null, steps: [], labels: [], priority: "medium",
  status: "ready", automated_test_key: null, automated_name: null, created_by: 1, created_at: "2026-10-06T10:00:00Z",
  updated_by: null, updated_at: null, suites: [], source_path: PATH, gherkin: null, feature_name: "Login", ...extra,
});

function asRole(role: string) {
  server.use(http.get(P, () => HttpResponse.json({ id: 42, organization_id: 1, name: "Web", my_role: role })));
}

beforeEach(() => {
  asRole("member");
  server.use(
    http.get(`${P}/ci-target`, () => HttpResponse.json(TARGET)),
    http.get(`${P}/features/detail`, ({ request }) =>
      new URL(request.url).searchParams.get("path") === PATH
        ? HttpResponse.json(DETAIL)
        : HttpResponse.json({ detail: "Feature not found" }, { status: 404 })),
    http.post(`${P}/analytics/run-strip`, () => HttpResponse.json({
      runs: [{ id: 7, started_at: "2026-10-08T09:00:00Z", branch: "main" }], statuses: { [KEY]: ["failed"] },
    })),
  );
});

function renderAt(url = URL_) {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <Routes><Route path="/projects/:projectId/cases/feature" element={<FeaturePage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("the raw file shows with line numbers; each scenario line links its case", async () => {
  renderAt();
  expect(await screen.findByRole("heading", { level: 1, name: "Login" })).toBeInTheDocument();
  expect(screen.getByText(PATH)).toBeInTheDocument();
  const file = await screen.findByLabelText("Feature file");
  const lines = file.querySelectorAll(".gk-line");
  expect(lines).toHaveLength(8);
  expect(lines[3]).toHaveAttribute("data-line", "4");
  expect(lines[3]).toHaveTextContent("Scenario: Good password");
  expect(within(lines[3] as HTMLElement).getByRole("link", { name: "TC-12" })).toHaveAttribute("href", "/projects/42/cases/12");
  expect(within(lines[6] as HTMLElement).getByRole("link", { name: "TC-13" })).toHaveAttribute("href", "/projects/42/cases/13");
  // The linked case shows its run strip; the unlinked one says so
  expect(within(lines[3] as HTMLElement).getByRole("link", { name: /Last 1 run/ })).toBeInTheDocument();
  expect(within(lines[6] as HTMLElement).getByText("not linked")).toBeInTheDocument();
  expect(screen.queryByText(/Re-import this file/)).not.toBeInTheDocument();
});

test("Run feature asks to run every scenario of the file", async () => {
  renderAt();
  await userEvent.click(await screen.findByRole("button", { name: "Run feature" }));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByRole("heading", { name: "Run 2 tests?" })).toBeInTheDocument();
  expect(within(dialog).getByText("TC-12 · Title 12")).toBeInTheDocument();
});

test("a viewer reads the file but has no Run feature", async () => {
  asRole("viewer");
  renderAt();
  await screen.findByLabelText("Feature file");
  expect(screen.queryByRole("button", { name: "Run feature" })).not.toBeInTheDocument();
});

test("without the stored file the scenarios are rebuilt from the cases, with a note", async () => {
  server.use(
    http.get(`${P}/features/detail`, () => HttpResponse.json({ ...DETAIL, content: null, imported_at: null,
      cases: DETAIL.cases.map((c) => ({ ...c, line: null })) })),
    http.get(`${P}/cases`, () => HttpResponse.json({ total: 3, items: [
      kase(12, { gherkin: "@smoke\nScenario: Good password\n  Given I type \"secret\"" }),
      kase(13, { gherkin: null }),
      kase(40, { source_path: "features/other.feature" }),
    ] })),
  );
  renderAt();
  expect(await screen.findByText("Re-import this file to see it exactly as written.")).toBeInTheDocument();
  const file = await screen.findByLabelText("Feature file");
  expect(file).toHaveTextContent("Feature: Login");
  expect(file).toHaveTextContent("Scenario: Good password");
  // A case with no stored Gherkin is shown by its title
  expect(file).toHaveTextContent("Scenario: Title 13");
  expect(file).not.toHaveTextContent("Title 40");
  const goodLine = [...file.querySelectorAll(".gk-line")].find((l) => l.textContent?.includes("Scenario: Good password"))!;
  expect(within(goodLine as HTMLElement).getByRole("link", { name: "TC-12" })).toBeInTheDocument();
});

test("an unknown or archived file says it is not found", async () => {
  renderAt("/projects/42/cases/feature?path=features%2Fgone.feature");
  expect(screen.getByRole("heading", { level: 1, name: "gone.feature" })).toBeInTheDocument();
  expect(await screen.findByText(/Feature not found/)).toBeInTheDocument();
});
