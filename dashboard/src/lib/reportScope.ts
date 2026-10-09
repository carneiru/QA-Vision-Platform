import type { CaseArea, CaseAreas } from "../api/cases";
import type { TestsSection } from "../api/report";

/** The report's joins (spec: Filters; ADR-026): area and suite filters become test keys from case-areas.
 *  Pure, so every rule is unit-tested. Phase 3 adds grouping by area. */

export type AreaKind = "feature" | "folder" | "label";
export interface AreaFilter {
  kind: AreaKind;
  value: string;
}
export const AREA_KINDS: AreaKind[] = ["feature", "folder", "label"];
export const AREA_NAMES: Record<AreaKind, string> = {
  feature: "Feature",
  folder: "Folder",
  label: "Label",
};

/** The most keys one report request carries (the cap of /cases/search too). */
export const MAX_REPORT_KEYS = 20_000;
const MAX_AREA_VALUE = 500;

/** "feature:Booking", "folder:features/booking" or "label:smoke"; anything else is null. */
export function parseArea(raw: string): AreaFilter | null {
  const colon = raw.indexOf(":");
  if (colon <= 0) return null;
  const kind = raw.slice(0, colon);
  let value = raw.slice(colon + 1);
  if (!(AREA_KINDS as string[]).includes(kind)) return null;
  if (kind === "folder") value = value.replace(/\/+$/, "");
  if (value === "" || value.length > MAX_AREA_VALUE || value.includes("\u0000"))
    return null;
  return { kind: kind as AreaKind, value };
}

export function formatArea(a: AreaFilter): string {
  return `${a.kind}:${a.value}`;
}

/** A folder includes its subfolders, matched on whole path segments (the Cases folder filter's rule). */
export function caseInArea(c: CaseArea, area: AreaFilter): boolean {
  if (area.kind === "feature") return c.feature === area.value;
  if (area.kind === "label")
    return c.labels.includes(area.value.toLowerCase());
  return (
    c.folder !== null &&
    (c.folder === area.value || c.folder.startsWith(`${area.value}/`))
  );
}

export type KeyScope =
  | { kind: "all" }
  | { kind: "keys"; keys: string[] }
  | { kind: "empty" }
  | { kind: "too_many"; count: number };

/** The test keys of the automated cases in the area and the suite (AND). Unlinked cases drop out. */
export function resolveScope(
  areas: CaseAreas,
  area: AreaFilter | null,
  suiteId: number | null
): KeyScope {
  if (area === null && suiteId === null) return { kind: "all" };
  const keys = new Set<string>();
  for (const c of areas.cases) {
    if (!c.testKey) continue;
    if (area && !caseInArea(c, area)) continue;
    if (suiteId !== null && !c.suiteIds.includes(suiteId)) continue;
    keys.add(c.testKey.toLowerCase());
  }
  if (keys.size === 0) return { kind: "empty" };
  if (keys.size > MAX_REPORT_KEYS)
    return { kind: "too_many", count: keys.size };
  return { kind: "keys", keys: [...keys].sort() };
}

/** Every folder and its ancestors with the number of cases under it, sorted by path: FolderSelect's input. */
export function folderCounts(
  areas: CaseAreas
): { path: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const c of areas.cases) {
    if (!c.folder) continue;
    const parts = c.folder.split("/");
    for (let i = 1; i <= parts.length; i++) {
      const path = parts.slice(0, i).join("/");
      counts.set(path, (counts.get(path) ?? 0) + 1);
    }
  }
  return [...counts]
    .map(([path, count]) => ({ path, count }))
    .sort((a, b) => a.path.localeCompare(b.path));
}

export type Grouping = "feature" | "folder" | "label" | "suite";
export const GROUPINGS: Grouping[] = ["feature", "folder", "label", "suite"];

export interface TestRow {
  testKey: string;
  executions: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  flips: number;
  pairs: number;
  durationMsSum: number;
  lastStatus: string | null;
}

/** The tests section's rows, read by column name so a new column never shifts the others. */
export function decodeTests(t: TestsSection): TestRow[] {
  const at = (name: string) => t.columns.indexOf(name);
  const i = {
    key: at("test_key"), executions: at("executions"), passed: at("passed"), failed: at("failed"), errored: at("errored"),
    skipped: at("skipped"), flips: at("flips"), pairs: at("pairs"), duration: at("duration_ms_sum"), last: at("last_status"),
  };
  const n = (row: (string | number | null)[], index: number) => Number(row[index] ?? 0);
  return t.rows.map((row) => ({
    testKey: String(row[i.key]).toLowerCase(), executions: n(row, i.executions), passed: n(row, i.passed),
    failed: n(row, i.failed), errored: n(row, i.errored), skipped: n(row, i.skipped), flips: n(row, i.flips),
    pairs: n(row, i.pairs), durationMsSum: n(row, i.duration), lastStatus: row[i.last] === null ? null : String(row[i.last]),
  }));
}

/** The Flaky page's defaults applied to the flips signal (spec: Section 3; plan Ruling 7). */
const FLAKY_MIN_OUTCOMES = 5;
const FLAKY_MIN_FLIP_RATE = 0.3;
export const FEW_RUNS = 10;

export function isFlaky(r: TestRow): boolean {
  return r.executions - r.skipped >= FLAKY_MIN_OUTCOMES && r.pairs > 0 && r.flips / r.pairs >= FLAKY_MIN_FLIP_RATE;
}

export interface AreaStats {
  key: string;
  label: string;
  linkedTests: number;
  testsRun: number;
  executions: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  passRate: number | null;
  failures: number;
  failingTests: number;
  flakyTests: number;
  durationMsSum: number;
  fewRuns: boolean;
}

export function folderAtDepth(folder: string, depth: number): string {
  return folder.split("/").slice(0, depth).join("/");
}

export function maxFolderDepth(areas: CaseAreas): number {
  return Math.max(1, ...areas.cases.filter((c) => c.folder).map((c) => c.folder!.split("/").length));
}

/** The shallowest depth that gives at least two folder groups; the deepest when none does. */
export function defaultFolderDepth(areas: CaseAreas): number {
  const deepest = maxFolderDepth(areas);
  for (let depth = 1; depth <= deepest; depth++) {
    const groups = new Set(areas.cases.filter((c) => c.folder).map((c) => folderAtDepth(c.folder!, depth)));
    if (groups.size >= 2) return depth;
  }
  return deepest;
}

export function groupsOf(c: CaseArea, grouping: Grouping, depth: number, suites: Map<number, string>): { key: string; label: string }[] {
  if (grouping === "feature") return c.feature ? [{ key: `feature:${c.feature}`, label: c.feature }] : [];
  if (grouping === "folder") {
    if (!c.folder) return [];
    const path = folderAtDepth(c.folder, depth);
    return [{ key: `folder:${path}`, label: path }];
  }
  if (grouping === "label") return c.labels.map((l) => ({ key: `label:${l}`, label: l }));
  return c.suiteIds.map((id) => ({ key: `suite:${id}`, label: suites.get(id) ?? `#${id}` }));
}

function empty(key: string, label: string): AreaStats {
  return { key, label, linkedTests: 0, testsRun: 0, executions: 0, passed: 0, failed: 0, errored: 0, skipped: 0,
    passRate: null, failures: 0, failingTests: 0, flakyTests: 0, durationMsSum: 0, fewRuns: true };
}

function add(stats: AreaStats, r: TestRow) {
  stats.testsRun += 1;
  stats.executions += r.executions;
  stats.passed += r.passed;
  stats.failed += r.failed;
  stats.errored += r.errored;
  stats.skipped += r.skipped;
  stats.failures += r.failed + r.errored;
  stats.failingTests += r.failed + r.errored > 0 ? 1 : 0;
  stats.flakyTests += isFlaky(r) ? 1 : 0;
  stats.durationMsSum += r.durationMsSum;
}

function finish(stats: AreaStats): AreaStats {
  const considered = stats.executions - stats.skipped;
  return { ...stats, passRate: considered > 0 ? stats.passed / considered : null, fewRuns: stats.executions < FEW_RUNS };
}

/** Ingestion's per-test rows grouped by the cases' areas. A test linked from cases in several groups (labels,
 *  suites, or two features) counts in each: the groups overlap and are not summed. */
export function groupByArea(areas: CaseAreas, rows: TestRow[], grouping: Grouping, depth: number):
  { groups: AreaStats[]; noCase: AreaStats | null } {
  const suites = new Map(areas.suites.map((s) => [s.id, s.name]));
  const groups = new Map<string, AreaStats>();
  const linked = new Map<string, Set<string>>(); // group key -> linked test keys
  const ofKey = new Map<string, Set<string>>(); // test key -> group keys
  const linkedKeys = new Set<string>();
  for (const c of areas.cases) {
    if (!c.testKey) continue;
    const key = c.testKey.toLowerCase();
    linkedKeys.add(key);
    for (const g of groupsOf(c, grouping, depth, suites)) {
      if (!groups.has(g.key)) groups.set(g.key, empty(g.key, g.label));
      if (!linked.has(g.key)) linked.set(g.key, new Set());
      linked.get(g.key)!.add(key);
      if (!ofKey.has(key)) ofKey.set(key, new Set());
      ofKey.get(key)!.add(g.key);
    }
  }
  let noCase: AreaStats | null = null;
  for (const r of rows) {
    if (!linkedKeys.has(r.testKey)) {
      noCase ??= empty("none", "No case");
      add(noCase, r);
      continue;
    }
    for (const g of ofKey.get(r.testKey) ?? []) add(groups.get(g)!, r);
  }
  const out = [...groups.values()].map((g) => finish({ ...g, linkedTests: linked.get(g.key)?.size ?? 0 }));
  return { groups: sortWorstFirst(out), noCase: noCase ? finish(noCase) : null };
}

/** Lowest pass rate first among areas with at least FEW_RUNS executions, then most failures; the others last. */
export function sortWorstFirst(groups: AreaStats[]): AreaStats[] {
  return [...groups].sort((a, b) => {
    if (a.fewRuns !== b.fewRuns) return a.fewRuns ? 1 : -1;
    const rate = (a.passRate ?? 2) - (b.passRate ?? 2);
    if (rate !== 0) return rate;
    if (a.failures !== b.failures) return b.failures - a.failures;
    return a.label.localeCompare(b.label);
  });
}

/** Automated cases (in the area and suite filters) whose test did not run in the period, by case number. */
export function neverRun(areas: CaseAreas, rows: TestRow[], scope: KeyScope): CaseArea[] {
  const ran = new Set(rows.map((r) => r.testKey));
  const inScope = scope.kind === "keys" ? new Set(scope.keys) : null;
  return areas.cases
    .filter((c) => c.testKey && !ran.has(c.testKey.toLowerCase()) && (!inScope || inScope.has(c.testKey.toLowerCase())))
    .sort((a, b) => a.number - b.number);
}

export function unlinkedTestCount(areas: CaseAreas, rows: TestRow[]): number {
  const linked = new Set(areas.cases.filter((c) => c.testKey).map((c) => c.testKey!.toLowerCase()));
  return rows.filter((r) => !linked.has(r.testKey)).length;
}
