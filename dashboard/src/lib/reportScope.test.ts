import { describe, expect, test } from "vitest";
import type { CaseArea, CaseAreas } from "../api/cases";
import type { TestsSection } from "../api/report";
import {
  MAX_REPORT_KEYS,
  decodeTests,
  defaultFolderDepth,
  folderAtDepth,
  folderCounts,
  formatArea,
  groupByArea,
  isFlaky,
  neverRun,
  parseArea,
  resolveScope,
  sortWorstFirst,
  unlinkedTestCount,
} from "./reportScope";

const k = (n: number) => n.toString(16).padStart(64, "0");

function area(number: number, over: Partial<CaseArea> = {}): CaseArea {
  return {
    number,
    title: `case ${number}`,
    testKey: k(number),
    folder: null,
    feature: null,
    labels: [],
    suiteIds: [],
    ...over,
  };
}

const AREAS: CaseAreas = {
  generatedAt: "2026-10-08T14:02:11Z",
  counts: { cases: 5, linked: 4, manual: 1 },
  folders: ["features/booking", "features/booking/air", "features/bookingx"],
  features: ["Air", "Booking"],
  labels: ["smoke"],
  suites: [{ id: 12, name: "Regression" }],
  cases: [
    area(1, {
      folder: "features/booking",
      feature: "Booking",
      labels: ["smoke"],
      suiteIds: [12],
    }),
    area(2, { folder: "features/booking/air", feature: "Air", suiteIds: [12] }),
    area(3, { folder: "features/bookingx", feature: "Booking" }),
    area(4, {
      testKey: null,
      folder: "features/booking",
      feature: "Booking",
      suiteIds: [12],
    }),
    area(5, { testKey: k(1), feature: "Air" }), // a second case linked to the same test
  ],
};

describe("reportScope", () => {
  test("areas parse and format; malformed ones are null", () => {
    expect(parseArea("feature:Air booking")).toEqual({
      kind: "feature",
      value: "Air booking",
    });
    expect(parseArea("folder:features/booking/")).toEqual({
      kind: "folder",
      value: "features/booking",
    });
    expect(formatArea({ kind: "label", value: "smoke" })).toBe("label:smoke");
    for (const bad of [
      "",
      "feature:",
      "bogus:x",
      "nocolon",
      `feature:${"x".repeat(501)}`,
    ])
      expect(parseArea(bad)).toBeNull();
  });

  test("no area and no suite is every test", () => {
    expect(resolveScope(AREAS, null, null)).toEqual({ kind: "all" });
  });

  test("feature, folder (with subfolders, whole segments) and label resolve to linked keys only", () => {
    expect(
      resolveScope(AREAS, { kind: "feature", value: "Booking" }, null)
    ).toEqual({ kind: "keys", keys: [k(1), k(3)] });
    expect(
      resolveScope(AREAS, { kind: "folder", value: "features/booking" }, null)
    ).toEqual({ kind: "keys", keys: [k(1), k(2)] });
    expect(resolveScope(AREAS, { kind: "label", value: "SMOKE" }, null)).toEqual(
      { kind: "keys", keys: [k(1)] }
    );
  });

  test("a suite alone and combined with an area", () => {
    expect(resolveScope(AREAS, null, 12)).toEqual({
      kind: "keys",
      keys: [k(1), k(2)],
    });
    expect(
      resolveScope(AREAS, { kind: "feature", value: "Air" }, 12)
    ).toEqual({ kind: "keys", keys: [k(2)] });
  });

  test("nothing linked is empty; more than 20,000 keys is too many", () => {
    expect(resolveScope(AREAS, { kind: "feature", value: "Nothing" }, null)).toEqual(
      { kind: "empty" }
    );
    const many: CaseAreas = {
      ...AREAS,
      cases: Array.from({ length: MAX_REPORT_KEYS + 1 }, (_, i) =>
        area(i + 1, { feature: "Big" })
      ),
    };
    expect(
      resolveScope(many, { kind: "feature", value: "Big" }, null)
    ).toEqual({ kind: "too_many", count: MAX_REPORT_KEYS + 1 });
  });

  test("folder counts include subfolders, for the folder picker", () => {
    expect(folderCounts(AREAS)).toEqual([
      { path: "features", count: 4 },
      { path: "features/booking", count: 3 },
      { path: "features/booking/air", count: 1 },
      { path: "features/bookingx", count: 1 },
    ]);
  });
});

const COLUMNS = ["test_key", "executions", "passed", "failed", "errored", "skipped", "flips", "pairs", "duration_ms_sum", "last_status"];
const tests = (rows: (string | number | null)[][]): TestsSection => ({ columns: COLUMNS, rows, truncated: false });
// k(1) is linked from case 1 (Booking, features/booking, smoke, suite 12) and case 5 (Air); k(2) from case 2 (Air, .../air, suite 12)
const ROWS = tests([
  [k(1), 20, 18, 2, 0, 0, 6, 19, 4000, "passed"],
  [k(2), 4, 2, 2, 0, 0, 0, 3, 1000, "failed"],
  [k(9), 10, 10, 0, 0, 0, 0, 9, 500, "passed"], // linked to no case
]);

describe("reportScope grouping", () => {
  test("rows decode by column name and flaky needs 5 outcomes and a flip rate of 0.3", () => {
    const [first] = decodeTests(ROWS);
    expect(first).toEqual({ testKey: k(1), executions: 20, passed: 18, failed: 2, errored: 0, skipped: 0, flips: 6, pairs: 19,
      durationMsSum: 4000, lastStatus: "passed" });
    expect(isFlaky(first)).toBe(true); // 6 / 19 >= 0.3, 20 outcomes
    expect(isFlaky({ ...first, flips: 5 })).toBe(false);
    expect(isFlaky({ ...first, executions: 4, skipped: 0, flips: 3, pairs: 3 })).toBe(false);
  });

  test("folders cut to a depth; the default depth is the shallowest with two groups", () => {
    expect(folderAtDepth("features/booking/air", 2)).toBe("features/booking");
    expect(folderAtDepth("features", 3)).toBe("features");
    expect(defaultFolderDepth(AREAS)).toBe(2); // depth 1 is all "features"
  });

  test("by feature: a test linked from two features counts in both; unlinked tests form No case", () => {
    const { groups, noCase } = groupByArea(AREAS, decodeTests(ROWS), "feature", 1);
    const air = groups.find((g) => g.label === "Air")!;
    const booking = groups.find((g) => g.label === "Booking")!;
    expect(air).toMatchObject({ linkedTests: 2, testsRun: 2, executions: 24, failures: 4, failingTests: 2, flakyTests: 1, fewRuns: false });
    expect(air.passRate).toBeCloseTo(20 / 24);
    expect(booking).toMatchObject({ linkedTests: 2, testsRun: 1, executions: 20 }); // k(3) never ran
    expect(noCase).toMatchObject({ label: "No case", testsRun: 1, executions: 10 });
  });

  test("by label and by suite; by folder at a depth", () => {
    expect(groupByArea(AREAS, decodeTests(ROWS), "label", 1).groups.map((g) => g.label)).toEqual(["smoke"]);
    const suite = groupByArea(AREAS, decodeTests(ROWS), "suite", 1).groups;
    expect(suite.map((g) => [g.key, g.label, g.testsRun])).toEqual([["suite:12", "Regression", 2]]);
    const folders = groupByArea(AREAS, decodeTests(ROWS), "folder", 2).groups.map((g) => g.label).sort();
    expect(folders).toEqual(["features/booking", "features/bookingx"]);
  });

  test("worst first: lowest pass rate among areas with 10+ executions, then most failures; few runs last", () => {
    const a = { key: "a", label: "a", passRate: 0.9, executions: 50, failures: 5, fewRuns: false };
    const b = { key: "b", label: "b", passRate: 0.5, executions: 12, failures: 6, fewRuns: false };
    const c = { key: "c", label: "c", passRate: 0.0, executions: 3, failures: 3, fewRuns: true };
    const d = { key: "d", label: "d", passRate: 0.9, executions: 40, failures: 9, fewRuns: false };
    const sorted = sortWorstFirst([a, b, c, d].map((x) => ({ linkedTests: 0, testsRun: 0, passed: 0, failed: 0, errored: 0,
      skipped: 0, failingTests: 0, flakyTests: 0, durationMsSum: 0, ...x })));
    expect(sorted.map((g) => g.key)).toEqual(["b", "d", "a", "c"]);
  });

  test("automated cases never run, in scope; and the count of tests without a case", () => {
    const rows = decodeTests(ROWS);
    expect(neverRun(AREAS, rows, { kind: "all" }).map((c) => c.number)).toEqual([3]);
    expect(neverRun(AREAS, rows, { kind: "keys", keys: [k(1), k(2)] })).toEqual([]);
    expect(unlinkedTestCount(AREAS, rows)).toBe(1);
  });
});
