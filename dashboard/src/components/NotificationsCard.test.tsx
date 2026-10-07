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
    on_failure: true, weekly_summary: false,
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
  // Pasted, not typed key by key: a long URL typed under a loaded test run outlasts the timeout
  await userEvent.click(screen.getByLabelText(/webhook url/i));
  await userEvent.paste("https://prod-1.westeurope.logic.azure.com/x");
  await userEvent.click(screen.getByLabelText(/only branch/i));
  await userEvent.paste("main");
  await userEvent.click(screen.getByRole("button", { name: /add channel/i }));
  expect(await screen.findByText("hooks.slack.com/…abcd")).toBeInTheDocument();
  expect(sent).toEqual({
    name: "Web", kind: "teams", url: "https://prod-1.westeurope.logic.azure.com/x", branch: "main",
    on_failure: true, weekly_summary: false,
  });
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

test("an email channel takes addresses instead of a webhook URL", async () => {
  let sent: unknown = null;
  server.use(
    http.get(BASE, () => HttpResponse.json([])),
    http.post(BASE, async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json(channel({ kind: "email", target: "qa@example.com" }), { status: 201 });
    }),
  );
  renderCard();
  await screen.findByText(/no channels yet/i);
  await userEvent.selectOptions(screen.getByLabelText(/^send to/i), "email");
  expect(screen.queryByLabelText(/webhook url/i)).not.toBeInTheDocument();
  const addresses = screen.getByLabelText(/email addresses/i);
  expect(addresses).toHaveAttribute("type", "email");
  expect(addresses).toHaveAttribute("multiple");
  expect(screen.getByText(/smtp/i)).toBeInTheDocument();
  await userEvent.type(addresses, "qa@example.com,lead@example.com");
  await userEvent.click(screen.getByRole("button", { name: /add channel/i }));
  await vi.waitFor(() =>
    expect(sent).toEqual({
      name: "Web", kind: "email", url: "qa@example.com,lead@example.com", on_failure: true, weekly_summary: false,
    }));
});

test("each channel shows what it sends; switching weekly on is a PATCH", async () => {
  let patched: unknown = null;
  server.use(
    http.get(BASE, () => HttpResponse.json([channel()])),
    http.patch(`${BASE}/1`, async ({ request }) => {
      patched = await request.json();
      return HttpResponse.json(channel({ weekly_summary: true }));
    }),
  );
  renderCard();
  const failed = await screen.findByRole("checkbox", { name: /failed runs to web/i });
  expect(failed).toBeChecked();
  const weekly = screen.getByRole("checkbox", { name: /weekly summary to web/i });
  expect(weekly).not.toBeChecked();
  await userEvent.click(weekly);
  expect(patched).toEqual({ weekly_summary: true });
});

test("a new channel can ask for the weekly summary only", async () => {
  let sent: Record<string, unknown> | null = null;
  server.use(
    http.get(BASE, () => HttpResponse.json([])),
    http.post(BASE, async ({ request }) => {
      sent = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(channel(), { status: 201 });
    }),
  );
  renderCard();
  await screen.findByText(/no channels yet/i);
  await userEvent.type(screen.getByLabelText(/webhook url/i), "https://hooks.slack.com/services/T/B/x");
  await userEvent.click(screen.getByRole("checkbox", { name: /^failed runs$/i }));
  await userEvent.click(screen.getByRole("checkbox", { name: /^weekly summary/i }));
  await userEvent.click(screen.getByRole("button", { name: /add channel/i }));
  await vi.waitFor(() => expect(sent).not.toBeNull());
  expect(sent).toMatchObject({ on_failure: false, weekly_summary: true });
});

test("send last week's summary on demand", async () => {
  let message: string | null = null;
  server.use(
    http.get(BASE, () => HttpResponse.json([channel({ weekly_summary: true })])),
    http.post(`${BASE}/1/test`, ({ request }) => {
      message = new URL(request.url).searchParams.get("message");
      return HttpResponse.json({ status: "delivered", error: null });
    }),
  );
  renderCard();
  await userEvent.click(await screen.findByRole("button", { name: /send last week's summary to web/i }));
  expect(await screen.findByText(/summary to web delivered/i)).toBeInTheDocument();
  expect(message).toBe("weekly");
});

test("on phones the table becomes stacked rows: every cell carries its column name", async () => {
  server.use(http.get(BASE, () => HttpResponse.json([channel()])));
  renderCard();
  const row = (await screen.findByText("hooks.slack.com/…abcd")).closest("tr")!;
  expect(row.closest("table")).toHaveClass("stacked");
  const labels = Array.from(row.querySelectorAll("td[data-label]")).map((td) => td.getAttribute("data-label"));
  expect(labels).toEqual(["Sends to", "Branch", "Sends", "Last delivery"]);
  // The Actions cell stays reachable
  expect(within(row).getByRole("button", { name: "Send a test message to Web" })).toBeInTheDocument();
});
