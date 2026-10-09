import type { CaseArea, CaseAreas } from "../api/cases";

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
