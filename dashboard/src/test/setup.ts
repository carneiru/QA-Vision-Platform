import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./server";

// Node's fetch (undici) rejects relative URLs, but the app only uses
// same-origin relative paths. Resolve them against jsdom's origin so MSW
// can intercept them.
const realFetch = globalThis.fetch;
globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
  typeof input === "string" && input.startsWith("/")
    ? realFetch(new URL(input, window.location.origin), init)
    : realFetch(input, init)) as typeof fetch;

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  sessionStorage.clear();
});
afterAll(() => server.close());
