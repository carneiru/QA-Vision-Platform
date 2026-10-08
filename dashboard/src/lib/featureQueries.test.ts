import { fileLabel, groupByFeature, worstPerRun } from "./featureQueries";
import type { Case } from "../api/cases";

const kase = (number: number, extra: Partial<Case>) => ({
  number, key: `TC-${number}`, title: `Case ${number}`, priority: "medium", status: "draft", automated_test_key: null,
  source_path: null, feature_name: null, ...extra,
}) as unknown as Case;

test("fileLabel drops the path and a trailing .feature, in any case", () => {
  expect(fileLabel("a/b/foo_bar.feature")).toBe("foo_bar");
  expect(fileLabel("foo.FEATURE")).toBe("foo");
  expect(fileLabel("a/b/foo.feature.txt")).toBe("foo.feature.txt");
  expect(fileLabel("x.feature/y")).toBe("y");
});

test("worstPerRun takes the worst status per run: failed > rerun > passed > skipped > null", () => {
  expect(worstPerRun(3, [["passed", "skipped", null], ["failed", "passed", null]])).toEqual(["failed", "passed", null]);
  expect(worstPerRun(2, [["skipped", "rerun"], ["passed", "passed"]])).toEqual(["passed", "rerun"]);
  expect(worstPerRun(2, [])).toEqual([null, null]);
});

test("the client-side grouping fills test_keys with its cases' distinct keys, sorted", () => {
  const rows = groupByFeature([
    kase(1, { source_path: "a.feature", feature_name: "A", automated_test_key: "b".repeat(64) }),
    kase(2, { source_path: "a.feature", feature_name: "A", automated_test_key: "a".repeat(64) }),
    kase(3, { source_path: "a.feature", feature_name: "A", automated_test_key: "a".repeat(64) }),
    kase(4, { source_path: "a.feature", feature_name: "A" }),
    kase(5, {}),
  ]);
  expect(rows[0].test_keys).toEqual(["a".repeat(64), "b".repeat(64)]);
  expect(rows[1].test_keys).toEqual([]);
});
