import { formatPointLabel, formatTick } from "./chartFormat";

test("ticks are short, locale-formatted and read the date as a local day", () => {
  const d = new Date(2026, 2, 4);
  expect(formatTick("2026-03-04")).toBe(new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(d));
  expect(formatTick("2026-03-01", "month")).toBe(new Intl.DateTimeFormat(undefined, { month: "short", year: "2-digit" }).format(new Date(2026, 2, 1)));
  expect(formatTick("not a date")).toBe("not a date");
});

test("point labels say what the point is", () => {
  expect(formatPointLabel("2026-03-04", "week")).toMatch(/^Week of /);
  expect(formatPointLabel("2026-03-01", "month")).toBe(new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(new Date(2026, 2, 1)));
  expect(formatPointLabel("2026-03-04", "day")).toContain("2026");
});
