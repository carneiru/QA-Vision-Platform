import { nextSort, parseSort, sortRows } from "./sort";

const KEYS = ["a", "b"] as const;
const FALLBACK = { key: "a", dir: "desc" } as const;

test("parseSort falls back on junk and keeps valid pairs", () => {
  expect(parseSort(null, null, KEYS, FALLBACK)).toEqual({ key: "a", dir: "desc" });
  expect(parseSort("zzz", "asc", KEYS, FALLBACK)).toEqual({ key: "a", dir: "asc" });
  expect(parseSort("b", "sideways", KEYS, FALLBACK)).toEqual({ key: "b", dir: "asc" });
  expect(parseSort("b", "desc", KEYS, FALLBACK)).toEqual({ key: "b", dir: "desc" });
});

test("nextSort flips the active column and starts a new one in its first direction", () => {
  expect(nextSort({ key: "a", dir: "desc" }, "a", "desc")).toEqual({ key: "a", dir: "asc" });
  expect(nextSort({ key: "a", dir: "asc" }, "a", "desc")).toEqual({ key: "a", dir: "desc" });
  expect(nextSort({ key: "a", dir: "asc" }, "b", "desc")).toEqual({ key: "b", dir: "desc" });
});

test("sortRows orders numbers and text, puts missing values last either way, and is stable", () => {
  const rows = [{ n: 2, s: "b10" }, { n: null, s: "b2" }, { n: 1, s: "B1" }, { n: 2, s: "z" }];
  const get = (r: (typeof rows)[number], k: "n" | "s") => r[k];
  expect(sortRows(rows, { key: "n", dir: "asc" }, get).map((r) => r.s)).toEqual(["B1", "b10", "z", "b2"]);
  expect(sortRows(rows, { key: "n", dir: "desc" }, get).map((r) => r.s)).toEqual(["b10", "z", "B1", "b2"]);
  expect(sortRows(rows, { key: "s", dir: "asc" }, get).map((r) => r.s)).toEqual(["B1", "b2", "b10", "z"]);
});
