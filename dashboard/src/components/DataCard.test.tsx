import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import type { Project } from "../api/orgs";
import DataCard from "./DataCard";

const FREE: Project = {
  id: 42, name: "Web", organization_id: 1, my_role: "owner",
  settings: { result_retention_days: 30 }, legal_hold: null,
};
const HELD: Project = {
  ...FREE, legal_hold: { since: "2026-10-05T10:00:00Z", by: 7, reason: "Audit 2026-Q4" },
};

function renderCard(project: Project, canManage = true) {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(["project", 42], project);
  render(
    <QueryClientProvider client={qc}>
      <DataCard project={project} canManage={canManage} />
    </QueryClientProvider>,
  );
}

test("says how long results are kept and that nothing is on hold", () => {
  renderCard(FREE);
  expect(screen.getByText(/30 days/)).toBeInTheDocument();
  expect(screen.getByText(/not on legal hold/i)).toBeInTheDocument();
});

test("placing a hold sends the reason and shows the hold in words", async () => {
  let sent: unknown = null;
  server.use(
    http.put("/api/v1/projects/42/legal-hold", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json(HELD);
    }),
  );
  renderCard(FREE);
  await userEvent.type(screen.getByLabelText(/reason/i), "Audit 2026-Q4");
  await userEvent.click(screen.getByRole("button", { name: /place legal hold/i }));
  expect(await screen.findByText(/on legal hold since/i)).toBeInTheDocument();
  expect(screen.getByText(/audit 2026-q4/i)).toBeInTheDocument();
  expect(sent).toEqual({ reason: "Audit 2026-Q4" });
});

test("releasing asks first and spells out the consequence", async () => {
  let released = false;
  server.use(
    http.delete("/api/v1/projects/42/legal-hold", () => {
      released = true;
      return HttpResponse.json(FREE);
    }),
  );
  renderCard(HELD);
  await userEvent.click(screen.getByRole("button", { name: /release legal hold/i }));
  expect(screen.getByText(/deletes results older than 30 days/i)).toBeInTheDocument();
  expect(released).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: /^release$/i }));
  expect(await screen.findByText(/not on legal hold/i)).toBeInTheDocument();
  expect(released).toBe(true);
});

test("export downloads the project's results as a file", async () => {
  const createObjectURL = vi.fn(() => "blob:export");
  const revokeObjectURL = vi.fn();
  Object.assign(URL, { createObjectURL, revokeObjectURL });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  server.use(
    http.get("/api/v1/projects/42/export", () =>
      new HttpResponse('{"type":"export"}\n', { headers: { "Content-Type": "application/x-ndjson" } })),
  );
  renderCard(FREE);
  await userEvent.click(screen.getByRole("button", { name: /download all results/i }));
  await vi.waitFor(() => expect(click).toHaveBeenCalled());
  expect(createObjectURL).toHaveBeenCalled();
  click.mockRestore();
});

test("members see the hold and retention but cannot change or export", () => {
  renderCard(HELD, false);
  expect(screen.getByText(/on legal hold since/i)).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(screen.getByText(/only owners and admins/i)).toBeInTheDocument();
});
