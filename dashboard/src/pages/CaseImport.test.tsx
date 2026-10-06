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

test("the complete folder hint says what each setting does to deleted or renamed files", async () => {
  asRole("member");
  renderAt("/projects/42/cases/import");
  expect(await screen.findByText(/deleted or renamed \.feature file are left as they are/i)).toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("checkbox", { name: /complete features folder/i }));
  expect(screen.getByText(/not in this folder are archived/i)).toBeInTheDocument();
});

// --- complete folder (full=true) -------------------------------------------------------------

test("a complete folder sends full=true on preview and import, and the button says what it archives", async () => {
  asRole("member");
  const bodies: Record<string, unknown>[] = [];
  server.use(http.post(`${P}/cases/import`, async ({ request }) => {
    bodies.push((await request.json()) as Record<string, unknown>);
    return HttpResponse.json(preview);
  }));
  renderAt("/projects/42/cases/import");
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText(/choose folder/i), [featureFile("a.feature", "Feature: A", "f/a.feature")]);
  const full = screen.getByRole("checkbox", { name: /complete features folder/i });
  expect(full).not.toBeChecked();
  await user.click(full);
  await user.click(screen.getByRole("button", { name: /preview/i }));
  await user.click(await screen.findByRole("button", { name: /import 2 changes \(archives 1\)/i }));
  await screen.findByText(/imported: 1 created/i);
  expect(bodies.map((b) => b.full)).toEqual([true, true]);
});

test("without the complete folder option, imports keep full=false and the button names no archive", async () => {
  asRole("member");
  const bodies: Record<string, unknown>[] = [];
  const noArchive = { ...preview, summary: { ...preview.summary, archived: 0 }, items: preview.items.filter((i) => i.action !== "archive") };
  server.use(http.post(`${P}/cases/import`, async ({ request }) => {
    bodies.push((await request.json()) as Record<string, unknown>);
    return HttpResponse.json(noArchive);
  }));
  renderAt("/projects/42/cases/import");
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText(/choose folder/i), [featureFile("a.feature", "Feature: A", "f/a.feature")]);
  await user.click(screen.getByRole("button", { name: /preview/i }));
  expect(await screen.findByRole("button", { name: /^import 1 changes$/i })).toBeInTheDocument();
  expect(bodies[0].full).toBe(false);
});

test("archiving more than half of the imported cases shows a warning", async () => {
  asRole("member");
  const mass = { ...preview, summary: { created: 0, updated: 0, moved: 0, reactivated: 0, archived: 3, unchanged: 1, skipped: 0 } };
  server.use(http.post(`${P}/cases/import`, () => HttpResponse.json(mass)));
  renderAt("/projects/42/cases/import");
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText(/choose folder/i), [featureFile("a.feature", "Feature: A", "f/a.feature")]);
  await user.click(screen.getByRole("checkbox", { name: /complete features folder/i }));
  await user.click(screen.getByRole("button", { name: /preview/i }));
  expect(await screen.findByRole("alert", { name: /archive/i })).toHaveTextContent(/3 of 4 imported cases/i);
});

test("changing the complete folder option clears the preview", async () => {
  asRole("member");
  server.use(http.post(`${P}/cases/import`, () => HttpResponse.json(preview)));
  renderAt("/projects/42/cases/import");
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText(/choose folder/i), [featureFile("a.feature", "Feature: A", "f/a.feature")]);
  await user.click(screen.getByRole("button", { name: /preview/i }));
  expect(await screen.findByText("Pay")).toBeInTheDocument();
  await user.click(screen.getByRole("checkbox", { name: /complete features folder/i }));
  expect(screen.queryByText("Pay")).not.toBeInTheDocument();
});
