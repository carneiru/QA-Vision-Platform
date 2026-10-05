import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import MaskingCard from "./MaskingCard";

const BASE = "/api/v1/projects/42/masking-patterns";
const PATTERN = { id: 1, name: "customer_id", pattern: "CUST-\\d{6}", created_at: "2026-10-05T10:00:00Z" };

function renderCard(canEdit: boolean | undefined = true) {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MaskingCard projectId={42} canEdit={canEdit} />
    </QueryClientProvider>,
  );
}

async function fill(name: string, pattern: string) {
  await userEvent.type(screen.getByLabelText(/^name/i), name);
  // userEvent treats { and [ as key descriptors; paste keeps the pattern literal
  await userEvent.click(screen.getByLabelText(/^pattern/i));
  await userEvent.paste(pattern);
}

test("says what is masked already and lists the project's own patterns", async () => {
  server.use(http.get(BASE, () => HttpResponse.json([PATTERN])));
  renderCard();
  expect(screen.getByText(/passwords, tokens, keys, emails and card numbers/i)).toBeInTheDocument();
  const row = (await screen.findByText("customer_id")).closest("tr")!;
  expect(within(row).getByText("CUST-\\d{6}")).toBeInTheDocument();
});

test("preview shows the masked sample before anything is saved", async () => {
  let previewed: unknown = null;
  let saved = false;
  server.use(
    http.get(BASE, () => HttpResponse.json([])),
    http.post(`${BASE}/preview`, async ({ request }) => {
      previewed = await request.json();
      return HttpResponse.json({ masked: "order [REDACTED:customer_id]", matches: 1 });
    }),
    http.post(BASE, () => {
      saved = true;
      return HttpResponse.json(PATTERN, { status: 201 });
    }),
  );
  renderCard();
  await screen.findByText(/no patterns of its own/i);
  await fill("customer_id", "CUST-\\d{6}");
  await userEvent.type(screen.getByLabelText(/sample text/i), "order CUST-123456");
  await userEvent.click(screen.getByRole("button", { name: /preview/i }));

  const result = await screen.findByRole("status");
  expect(result).toHaveTextContent("order [REDACTED:customer_id]");
  expect(result).toHaveTextContent(/1 match/i);
  expect(previewed).toEqual({ name: "customer_id", pattern: "CUST-\\d{6}", sample: "order CUST-123456" });
  expect(saved).toBe(false);
});

test("adding saves the pattern, lists it and clears the form", async () => {
  let sent: unknown = null;
  let added = false;
  server.use(
    http.get(BASE, () => HttpResponse.json(added ? [PATTERN] : [])),
    http.post(BASE, async ({ request }) => {
      sent = await request.json();
      added = true;
      return HttpResponse.json(PATTERN, { status: 201 });
    }),
  );
  renderCard();
  await screen.findByText(/no patterns of its own/i);
  await fill("customer_id", "CUST-\\d{6}");
  await userEvent.click(screen.getByRole("button", { name: /add pattern/i }));

  expect(await screen.findByText("customer_id")).toBeInTheDocument();
  expect(sent).toEqual({ name: "customer_id", pattern: "CUST-\\d{6}" });
  expect(screen.getByLabelText(/^pattern/i)).toHaveValue("");
});

test("an unsafe pattern is explained and kept for editing", async () => {
  server.use(
    http.get(BASE, () => HttpResponse.json([])),
    http.post(BASE, () =>
      HttpResponse.json({ detail: "This pattern matches empty text; it must match at least one character" },
        { status: 422 })),
  );
  renderCard();
  await screen.findByText(/no patterns of its own/i);
  await fill("anything", "x*");
  await userEvent.click(screen.getByRole("button", { name: /add pattern/i }));
  expect(await screen.findByText(/matches empty text/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/^pattern/i)).toHaveValue("x*");
});

test("removing asks first, then deletes", async () => {
  let removed = false;
  server.use(
    http.get(BASE, () => HttpResponse.json(removed ? [] : [PATTERN])),
    http.delete(`${BASE}/1`, () => {
      removed = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  renderCard();
  await screen.findByText("customer_id");
  await userEvent.click(screen.getByRole("button", { name: /remove pattern customer_id/i }));
  expect(removed).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: /^remove$/i }));
  expect(await screen.findByText(/no patterns of its own/i)).toBeInTheDocument();
});

test("viewers read the patterns but cannot change them", async () => {
  server.use(http.get(BASE, () => HttpResponse.json([PATTERN])));
  renderCard(false);
  const row = (await screen.findByText("customer_id")).closest("tr")!;
  expect(within(row).queryByRole("button")).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/^pattern/i)).not.toBeInTheDocument();
});
