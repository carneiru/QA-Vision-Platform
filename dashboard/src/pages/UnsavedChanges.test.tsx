import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Link, RouterProvider, createMemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import CaseEditorPage from "./CaseEditorPage";
import SuiteDetailPage from "./SuiteDetailPage";

const P = "/api/v1/projects/42";
const KEY = "b".repeat(64);

const kase = (number: number, extra: object = {}) => ({
  number, key: `TC-${number}`, title: `Case ${number}`, description: null, steps: [{ action: "First", expected: "" }], labels: [],
  priority: "medium", status: "draft", automated_test_key: null, automated_name: null, created_by: 1,
  created_at: "2026-10-06T10:00:00Z", updated_by: null, updated_at: null, suites: [], source_path: null, gherkin: null,
  feature_name: null, ...extra,
});
const suiteBody = (extra: object = {}) => ({
  id: 5, name: "Smoke", description: null, case_count: 1, created_at: "2026-10-06T10:00:00Z", updated_at: null,
  cases: [{ number: 1, key: "TC-1", title: "Case 1", status: "draft", priority: "medium", labels: [], automated_test_key: null }],
  ...extra,
});
const emptyHistory = {
  test_key: KEY, suite: null, class_name: null, name: "pays",
  summary: { runs: 0, passed: 0, failed: 0, errored: 0, skipped: 0, pass_rate: 0, avg_duration_ms: 0 }, executions: [],
};

beforeEach(() => {
  setAccessToken("acc");
  server.use(
    http.get(P, () => HttpResponse.json({ id: 42, organization_id: 1, name: "Web", my_role: "member" })),
    http.get(`${P}/cases/3`, () => HttpResponse.json(kase(3))),
    http.get(`${P}/suites/5`, () => HttpResponse.json(suiteBody())),
  );
});

function renderPage(path: string, element: React.ReactNode, route: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      { path: route, element: <>{element}<Link to="/elsewhere">Elsewhere</Link></> },
      { path: "/elsewhere", element: <p>Elsewhere page</p> },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}
const editor = () => renderPage("/projects/42/cases/3", <CaseEditorPage />, "/projects/:projectId/cases/:caseNumber");
const suite = () => renderPage("/projects/42/suites/5", <SuiteDetailPage />, "/projects/:projectId/suites/:suiteId");

// --- case editor ---------------------------------------------------------------------------

test("Save is disabled until something changes, and the page says so while edits are unsaved", async () => {
  editor();
  const title = await screen.findByLabelText(/^title/i);
  const save = screen.getByRole("button", { name: /save changes/i });
  expect(save).toBeDisabled();
  expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();
  await userEvent.type(title, "!");
  expect(save).toBeEnabled();
  expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  await userEvent.type(title, "{Backspace}");
  expect(save).toBeDisabled();
});

test("leaving with unsaved edits asks first; Stay keeps the page and Leave goes", async () => {
  editor();
  await userEvent.type(await screen.findByLabelText(/^title/i), "!");
  await userEvent.click(screen.getByRole("link", { name: "Elsewhere" }));
  expect(await screen.findByRole("alertdialog", { name: /unsaved changes/i })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Stay" }));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(screen.getByLabelText(/^title/i)).toHaveValue("Case 3!");
  await userEvent.click(screen.getByRole("link", { name: "Elsewhere" }));
  await userEvent.click(await screen.findByRole("button", { name: /leave without saving/i }));
  expect(await screen.findByText("Elsewhere page")).toBeInTheDocument();
});

test("a clean editor leaves without asking", async () => {
  editor();
  await screen.findByLabelText(/^title/i);
  await userEvent.click(screen.getByRole("link", { name: "Elsewhere" }));
  expect(await screen.findByText("Elsewhere page")).toBeInTheDocument();
});

test("reloading or closing with unsaved edits triggers the browser prompt", async () => {
  editor();
  await userEvent.type(await screen.findByLabelText(/^title/i), "!");
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  expect(event.defaultPrevented).toBe(true);
});

test("saving clears the unsaved state, so leaving afterwards is not blocked", async () => {
  server.use(http.patch(`${P}/cases/3`, async ({ request }) => HttpResponse.json(kase(3, (await request.json()) as object))));
  editor();
  await userEvent.type(await screen.findByLabelText(/^title/i), "!");
  await userEvent.click(screen.getByRole("button", { name: /save changes/i }));
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "Elsewhere" }));
  expect(await screen.findByText("Elsewhere page")).toBeInTheDocument();
});

test("linking an automated test keeps the edits being typed", async () => {
  server.use(
    http.get(`${P}/analytics/tests`, () => HttpResponse.json([
      { test_key: KEY, suite: "checkout", class_name: "Cart", name: "pays", runs: 3, passed: 3, failed: 0, errored: 0,
        skipped: 0, pass_rate: 1, avg_duration_ms: 10, last_status: "passed", last_seen: "2026-10-06T10:00:00Z" },
    ])),
    http.patch(`${P}/cases/3`, async ({ request }) => HttpResponse.json(kase(3, (await request.json()) as object))),
    http.get(`${P}/analytics/tests/${KEY}/history`, () => HttpResponse.json(emptyHistory)),
  );
  editor();
  await userEvent.type(await screen.findByLabelText(/^title/i), " edited");
  await userEvent.type(screen.getByLabelText(/^action 1/i), " more");
  await userEvent.type(screen.getByLabelText(/find an automated test/i), "pays");
  await userEvent.click(screen.getByRole("button", { name: /^search$/i }));
  await userEvent.click(await screen.findByRole("button", { name: /link checkout › cart › pays/i }));
  expect(await screen.findByRole("button", { name: /unlink/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/^title/i)).toHaveValue("Case 3 edited");
  expect(screen.getByLabelText(/^action 1/i)).toHaveValue("First more");
  expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
});

test("unlinking asks first and keeps the edits being typed", async () => {
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.get(`${P}/cases/3`, () => HttpResponse.json(kase(3, patched ?? { automated_test_key: KEY, automated_name: "pays" }))),
    http.get(`${P}/analytics/tests/${KEY}/history`, () => HttpResponse.json(emptyHistory)),
    http.patch(`${P}/cases/3`, async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(kase(3, patched));
    }),
  );
  editor();
  await userEvent.type(await screen.findByLabelText(/^title/i), " edited");
  await userEvent.click(screen.getByRole("button", { name: "Unlink" }));
  expect(patched).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Unlink" }));
  expect(await screen.findByText(/find an automated test/i)).toBeInTheDocument();
  expect(patched).toEqual({ automated_test_key: null });
  expect(screen.getByLabelText(/^title/i)).toHaveValue("Case 3 edited");
});

// --- suite details -------------------------------------------------------------------------

test("a suite's Save buttons are disabled until something changes, and leaving asks first", async () => {
  suite();
  const saveDetails = await screen.findByRole("button", { name: "Save details" });
  expect(saveDetails).toBeDisabled();
  expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText(/^name/i), "!");
  expect(saveDetails).toBeEnabled();
  expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "Elsewhere" }));
  expect(await screen.findByRole("alertdialog", { name: /unsaved changes/i })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Stay" }));
  expect(screen.getByLabelText(/^name/i)).toHaveValue("Smoke!");
});

test("saving a suite's case order does not discard half-typed details", async () => {
  server.use(http.put(`${P}/suites/5/cases`, () => HttpResponse.json(suiteBody())));
  suite();
  await userEvent.type(await screen.findByLabelText(/^name/i), "!");
  await userEvent.click(screen.getByRole("button", { name: /remove tc-1 from the suite/i }));
  await userEvent.click(screen.getByRole("button", { name: /save order and cases/i }));
  await screen.findByRole("button", { name: "Saved" });
  expect(screen.getByLabelText(/^name/i)).toHaveValue("Smoke!");
});
