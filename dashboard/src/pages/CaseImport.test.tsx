import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import CaseImportPage from "./CaseImportPage";

const P = "/api/v1/projects/42";

function asRole(role: string) {
  server.use(http.get(P, () => HttpResponse.json({ id: 42, organization_id: 1, name: "Web", my_role: role })));
}

function renderAt(url: string) {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/projects/:projectId/cases/import" element={<CaseImportPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const preview = {
  plan_hash: "c".repeat(64),
  summary: { created: 1, updated: 0, moved: 0, reactivated: 0, archived: 1, unchanged: 1, skipped: 0 },
  items: [
    { action: "create", path: "tests/features/a.feature", scenario: "Pay", case_number: null },
    { action: "archive", path: "tests/features/a.feature", scenario: "Old", case_number: 3 },
    { action: "unchanged", path: "tests/features/a.feature", scenario: "Same", case_number: 2 },
  ],
  errors: [{ path: "tests/features/b.feature", line: 4, message: "(4:3): expected ..." }],
  warnings: [],
};

function featureFile(name: string, text: string, relative: string) {
  const file = new File([text], name, { type: "" });
  Object.defineProperty(file, "webkitRelativePath", { value: relative });
  return file;
}

test("previews the chosen .feature files with the prefix, then imports with the previewed hash", async () => {
  asRole("member");
  const bodies: { dry: string | null; json: Record<string, unknown> }[] = [];
  server.use(http.post(`${P}/cases/import`, async ({ request }) => {
    const url = new URL(request.url);
    const json = (await request.json()) as Record<string, unknown>;
    bodies.push({ dry: url.searchParams.get("dry_run"), json });
    return HttpResponse.json(url.searchParams.get("dry_run") === "true"
      ? preview : { ...preview, items: [{ ...preview.items[0], case_number: 9 }] });
  }));
  renderAt("/projects/42/cases/import");
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText(/choose folder/i), [
    featureFile("a.feature", "Feature: A", "features/a.feature"),
    featureFile("notes.md", "x", "features/notes.md"),
  ]);
  expect(await screen.findByText(/1 \.feature file/i)).toBeInTheDocument();
  await user.type(screen.getByLabelText(/path prefix/i), "tests/");
  await user.click(screen.getByRole("button", { name: /preview/i }));
  expect(await screen.findByText("Pay")).toBeInTheDocument();
  expect(screen.queryByText("Same")).not.toBeInTheDocument();        // unchanged hidden by default
  expect(screen.getByText(/\(4:3\)/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /import 2 changes/i }));
  expect(await screen.findByText(/imported: 1 created/i)).toBeInTheDocument();
  expect(bodies[0]).toEqual({ dry: "true", json: { files: [{ path: "tests/features/a.feature", content: "Feature: A" }], full: false } });
  expect(bodies[1].json.expected_plan_hash).toBe("c".repeat(64));
});

test("a plan that changed since the preview shows the new preview and says so", async () => {
  asRole("member");
  let calls = 0;
  server.use(http.post(`${P}/cases/import`, ({ request }) => {
    calls += 1;
    const dry = new URL(request.url).searchParams.get("dry_run") === "true";
    if (!dry) return HttpResponse.json({ detail: { code: "plan_changed", message: "Plan differs" } }, { status: 409 });
    return HttpResponse.json(calls === 1 ? preview : { ...preview, plan_hash: "d".repeat(64) });
  }));
  renderAt("/projects/42/cases/import");
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText(/choose folder/i), [featureFile("a.feature", "Feature: A", "f/a.feature")]);
  await user.click(screen.getByRole("button", { name: /preview/i }));
  await user.click(await screen.findByRole("button", { name: /import 2 changes/i }));
  expect(await screen.findByText(/something changed since your preview/i)).toBeInTheDocument();
  await vi.waitFor(() => expect(calls).toBe(3));
});

test("another running import shows the server's message", async () => {
  asRole("member");
  server.use(http.post(`${P}/cases/import`, ({ request }) => {
    const dry = new URL(request.url).searchParams.get("dry_run") === "true";
    if (!dry) return HttpResponse.json({ detail: { code: "import_conflict", message: "Another import is running; try again" } }, { status: 409 });
    return HttpResponse.json(preview);
  }));
  renderAt("/projects/42/cases/import");
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText(/choose folder/i), [featureFile("a.feature", "Feature: A", "f/a.feature")]);
  await user.click(screen.getByRole("button", { name: /preview/i }));
  await user.click(await screen.findByRole("button", { name: /import 2 changes/i }));
  expect(await screen.findByText(/another import is running/i)).toBeInTheDocument();
});

test("viewers do not get the import page's controls", async () => {
  asRole("viewer");
  renderAt("/projects/42/cases/import");
  expect(await screen.findByText(/only editors can import/i)).toBeInTheDocument();
  expect(screen.queryByLabelText(/choose folder/i)).not.toBeInTheDocument();
});

test("says that deleted or renamed files are not archived from here", async () => {
  asRole("member");
  renderAt("/projects/42/cases/import");
  expect(await screen.findByText(/deleted or renamed \.feature file are not archived or moved/i)).toBeInTheDocument();
});
