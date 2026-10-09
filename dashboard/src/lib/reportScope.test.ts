import { describe, expect, test } from "vitest";
import type { CaseArea, CaseAreas } from "../api/cases";
import {
  MAX_REPORT_KEYS,
  folderCounts,
  formatArea,
  parseArea,
  resolveScope,
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
