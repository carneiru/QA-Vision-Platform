import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import RepositoriesCard from "./RepositoriesCard";

const BASE = "/api/v1/projects/42/repositories";

function repo(overrides: Record<string, unknown>) {
  return {
    id: 1, project_id: 42, provider: "github", owner: "acme", name: "e2e-tests",
    url: "https://github.com/acme/e2e-tests", default_branch: "main",
    default_branch_is_user_set: false, verification_status: "verified",
    verified_at: "2026-10-05T10:00:00Z", created_at: "2026-10-05T10:00:00Z", updated_at: null,
    ...overrides,
  };
}

function renderCard(canEdit = true) {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <RepositoriesCard projectId={42} canEdit={canEdit} />
    </QueryClientProvider>,
  );
}

test("lists repositories with provider, link, branch and a worded status", async () => {
  server.use(
    http.get(BASE, () =>
      HttpResponse.json([
        repo({}),
        repo({ id: 2, provider: "gitlab", owner: "acme/qa", name: "api-tests",
               url: "https://gitlab.com/acme/qa/api-tests", verification_status: "not_found" }),
        repo({ id: 3, name: "mobile", url: "https://github.com/acme/mobile",
               default_branch: "develop", verification_status: "unchecked" }),
      ])),
  );
  renderCard();
  const link = await screen.findByRole("link", { name: /^acme\/e2e-tests/ });
  expect(link).toHaveAttribute("href", "https://github.com/acme/e2e-tests");
  expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  expect(screen.getByText("GitLab")).toBeInTheDocument();
  expect(screen.getByText("develop")).toBeInTheDocument();
  // status is words, not just a colour
  expect(screen.getByText("Reachable")).toBeInTheDocument();
  expect(screen.getByText(/not found or private/i)).toBeInTheDocument();
  expect(screen.getByText(/not checked/i)).toBeInTheDocument();
});

test("an empty project explains what to add", async () => {
  server.use(http.get(BASE, () => HttpResponse.json([])));
  renderCard();
  expect(await screen.findByText(/no repositories yet/i)).toBeInTheDocument();
});

test("adding a repository sends the URL and optional branch, then lists it", async () => {
  let sent: unknown = null;
  let added = false;
  server.use(
    http.get(BASE, () => HttpResponse.json(added ? [repo({ default_branch: "develop" })] : [])),
    http.post(BASE, async ({ request }) => {
      sent = await request.json();
      added = true;
      return HttpResponse.json(repo({ default_branch: "develop" }), { status: 201 });
    }),
  );
  renderCard();
  await screen.findByText(/no repositories yet/i);
  await userEvent.type(screen.getByLabelText(/repository url/i), "https://github.com/acme/e2e-tests");
  await userEvent.type(screen.getByLabelText(/default branch/i), "develop");
  await userEvent.click(screen.getByRole("button", { name: /add repository/i }));

  expect(await screen.findByRole("link", { name: /^acme\/e2e-tests/ })).toBeInTheDocument();
  expect(sent).toEqual({ url: "https://github.com/acme/e2e-tests", default_branch: "develop" });
  expect(screen.getByLabelText(/repository url/i)).toHaveValue("");
});

test("without a branch, none is sent so the provider's default is used", async () => {
  let sent: unknown = null;
  server.use(
    http.get(BASE, () => HttpResponse.json([])),
    http.post(BASE, async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json(repo({}), { status: 201 });
    }),
  );
  renderCard();
  await screen.findByText(/no repositories yet/i);
  await userEvent.type(screen.getByLabelText(/repository url/i), "git@github.com:acme/e2e-tests.git");
  await userEvent.click(screen.getByRole("button", { name: /add repository/i }));
  await vi.waitFor(() => expect(sent).toEqual({ url: "git@github.com:acme/e2e-tests.git" }));
});

test("a rejected URL is explained next to the form and kept for editing", async () => {
  server.use(
    http.get(BASE, () => HttpResponse.json([])),
    http.post(BASE, () =>
      HttpResponse.json({ detail: "Only github.com and gitlab.com repositories are supported" }, { status: 422 })),
  );
  renderCard();
  await screen.findByText(/no repositories yet/i);
  await userEvent.type(screen.getByLabelText(/repository url/i), "https://bitbucket.org/a/b");
  await userEvent.click(screen.getByRole("button", { name: /add repository/i }));
  expect(await screen.findByText(/only github\.com and gitlab\.com/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/repository url/i)).toHaveValue("https://bitbucket.org/a/b");
});

test("checking again asks the provider and shows the new status", async () => {
  let verified = false;
  server.use(
    http.get(BASE, () => HttpResponse.json([repo({ verification_status: verified ? "verified" : "unchecked" })])),
    http.post(`${BASE}/1/verify`, () => {
      verified = true;
      return HttpResponse.json(repo({}));
    }),
  );
  renderCard();
  await screen.findByText(/not checked/i);
  await userEvent.click(screen.getByRole("button", { name: /check acme\/e2e-tests again/i }));
  expect(await screen.findByText("Reachable")).toBeInTheDocument();
});

test("removing asks first, then deletes", async () => {
  let removed = false;
  server.use(
    http.get(BASE, () => HttpResponse.json(removed ? [] : [repo({})])),
    http.delete(`${BASE}/1`, () => {
      removed = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  renderCard();
  await screen.findByRole("link", { name: /^acme\/e2e-tests/ });
  await userEvent.click(screen.getByRole("button", { name: /remove acme\/e2e-tests/i }));
  expect(removed).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: /^remove$/i }));
  expect(await screen.findByText(/no repositories yet/i)).toBeInTheDocument();
});

test("viewers see the list but no way to change it", async () => {
  server.use(http.get(BASE, () => HttpResponse.json([repo({})])));
  renderCard(false);
  const row = (await screen.findByRole("link", { name: /^acme\/e2e-tests/ })).closest("tr")!;
  expect(within(row).queryByRole("button")).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/repository url/i)).not.toBeInTheDocument();
  expect(screen.getByText(/only owners, admins and members/i)).toBeInTheDocument();
});
