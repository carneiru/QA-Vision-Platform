import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import NotificationsCard from "./NotificationsCard";

const BASE = "/api/v1/projects/42/notification-channels";

function channel(overrides: Record<string, unknown> = {}) {
  return {
    id: 1, name: "Web", kind: "slack", target: "hooks.slack.com/…abcd", branch: "main", enabled: true,
    last_status: "delivered", last_error: null, last_sent_at: "2026-10-05T10:00:00Z", ...overrides,
  };
}

function renderCard(canEdit: boolean | undefined = true) {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <NotificationsCard projectId={42} projectName="Web" canEdit={canEdit} />
    </QueryClientProvider>,
  );
}

test("lists channels with kind, masked target, branch and last delivery in words", async () => {
  server.use(http.get(BASE, () => HttpResponse.json([
    channel(),
    channel({ id: 2, kind: "teams", name: "QA team", target: "prod-1.westeurope.logic.azure.com/…cr3t", branch: null,
              last_status: "failed", last_error: "The endpoint answered 404" }),
    channel({ id: 3, kind: "webhook", name: "Hook", target: "alerts.example.com/…hook", enabled: false, last_status: null, last_sent_at: null }),
  ])));
  renderCard();
  const slack = (await screen.findByText("hooks.slack.com/…abcd")).closest("tr")!;
  expect(within(slack).getByText("Slack")).toBeInTheDocument();
  expect(within(slack).getByText("main")).toBeInTheDocument();
  expect(within(slack).getByText(/delivered/i)).toBeInTheDocument();
  const teams = screen.getByText("QA team").closest("tr")!;
  expect(within(teams).getByText("Microsoft Teams")).toBeInTheDocument();
  expect(within(teams).getByText(/all branches/i)).toBeInTheDocument();
  expect(within(teams).getByText(/failed: the endpoint answered 404/i)).toBeInTheDocument();
  expect(screen.getByText(/paused/i)).toBeInTheDocument();
});

test("adding sends kind, name (prefilled with the project), URL and branch", async () => {
  let sent: unknown = null;
  let added = false;
  server.use(
    http.get(BASE, () => HttpResponse.json(added ? [channel()] : [])),
    http.post(BASE, async ({ request }) => {
      sent = await request.json();
      added = true;
      return HttpResponse.json(channel(), { status: 201 });
    }),
  );
  renderCard();
  await screen.findByText(/no channels yet/i);
  expect(screen.getByLabelText(/^name/i)).toHaveValue("Web");
  await userEvent.selectOptions(screen.getByLabelText(/^send to/i), "teams");
  expect(screen.getByText(/workflows/i)).toBeInTheDocument();      // per-kind helper text
  await userEvent.type(screen.getByLabelText(/webhook url/i), "https://prod-1.westeurope.logic.azure.com/x");
  await userEvent.type(screen.getByLabelText(/only branch/i), "main");
  await userEvent.click(screen.getByRole("button", { name: /add channel/i }));
  expect(await screen.findByText("hooks.slack.com/…abcd")).toBeInTheDocument();
  expect(sent).toEqual({ name: "Web", kind: "teams", url: "https://prod-1.westeurope.logic.azure.com/x", branch: "main" });
  expect(screen.getByLabelText(/webhook url/i)).toHaveValue("");
});

test("a refused URL is explained and kept", async () => {
  server.use(
    http.get(BASE, () => HttpResponse.json([])),
    http.post(BASE, () => HttpResponse.json({ detail: "The URL must point to a public address" }, { status: 422 })),
  );
  renderCard();
  await screen.findByText(/no channels yet/i);
  await userEvent.selectOptions(screen.getByLabelText(/^send to/i), "webhook");
  await userEvent.type(screen.getByLabelText(/webhook url/i), "https://10.0.0.1/x");
  await userEvent.click(screen.getByRole("button", { name: /add channel/i }));
  expect(await screen.findByText(/public address/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/webhook url/i)).toHaveValue("https://10.0.0.1/x");
});

test("send test shows the outcome next to the channel", async () => {
  server.use(
    http.get(BASE, () => HttpResponse.json([channel()])),
    http.post(`${BASE}/1/test`, () => HttpResponse.json({ status: "failed", error: "The endpoint answered 404" })),
  );
  renderCard();
  await screen.findByText("hooks.slack.com/…abcd");
  await userEvent.click(screen.getByRole("button", { name: /send a test message to web/i }));
  expect(await screen.findByRole("status")).toHaveTextContent(/test to web failed: the endpoint answered 404/i);
});

test("pause and resume", async () => {
  let enabled = true;
  let sent: unknown = null;
  server.use(
    http.get(BASE, () => HttpResponse.json([channel({ enabled })])),
    http.patch(`${BASE}/1`, async ({ request }) => {
      sent = await request.json();
      enabled = (sent as { enabled: boolean }).enabled;
      return HttpResponse.json(channel({ enabled }));
    }),
  );
  renderCard();
  await userEvent.click(await screen.findByRole("button", { name: /pause web/i }));
  expect(sent).toEqual({ enabled: false });
  expect(await screen.findByRole("button", { name: /resume web/i })).toBeInTheDocument();
});

test("removing asks first", async () => {
  let removed = false;
  server.use(
    http.get(BASE, () => HttpResponse.json(removed ? [] : [channel()])),
    http.delete(`${BASE}/1`, () => {
      removed = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  renderCard();
  await userEvent.click(await screen.findByRole("button", { name: /remove web/i }));
  expect(removed).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: /^remove$/i }));
  expect(await screen.findByText(/no channels yet/i)).toBeInTheDocument();
});

test("viewers read but cannot change", async () => {
  server.use(http.get(BASE, () => HttpResponse.json([channel()])));
  renderCard(false);
  const row = (await screen.findByText("hooks.slack.com/…abcd")).closest("tr")!;
  expect(within(row).queryByRole("button")).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/webhook url/i)).not.toBeInTheDocument();
});
