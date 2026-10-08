import { type Case, type CaseQuery, type FeatureGroup, getFeatureDetail, listCases } from "../api/cases";
import type { CaseRowData } from "../components/CaseTable";

/** A page of the Feature view. */
export const FEATURES_PAGE = 50;
/** The most cases one feature row shows when expanded, and the most a fallback grouping reads. */
export const GROUP_CASES_MAX = 200;

/** A feature group, with its cases when the page grouped them itself (filters the feature list cannot apply). */
export interface FeatureRow extends FeatureGroup {
  cases?: CaseRowData[];
}

export const featureDetailQuery = (projectId: number, path: string) => ({
  queryKey: ["feature", projectId, path] as const,
  queryFn: () => getFeatureDetail(projectId, path),
});

/** The folder of a repo-relative path, "" at the root (as the server reports it). */
export const folderOf = (path: string | null) => (path == null ? null : path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "");

/** The scenarios a feature row expands to, in file order. A file's come from its detail, kept to the row's
 *  filtered case numbers; the manual group's from /cases with the same filters (manual cases have no file). */
export const groupCasesQuery = (projectId: number, row: FeatureRow, filters: Omit<CaseQuery, "limit" | "offset">) => ({
  queryKey: ["feature-cases", projectId, row.path, row.feature_name, row.case_numbers, filters] as const,
  queryFn: async (): Promise<CaseRowData[]> => {
    if (row.cases) return row.cases;
    const wanted = new Set(row.case_numbers);
    if (row.path != null) {
      const detail = await getFeatureDetail(projectId, row.path);
      return detail.cases.filter((c) => wanted.has(c.number)).map((c) => ({ ...c, source_path: detail.path }));
    }
    const page = await listCases(projectId, { ...filters, origin: "manual", limit: GROUP_CASES_MAX, offset: 0 });
    return page.items.filter((c) => c.source_path == null);
  },
  staleTime: 30_000,
});

/** Groups cases the way GET /features does: by (feature name, path), ordered by folder then name, manual last. */
export function groupByFeature(cases: Case[]): FeatureRow[] {
  const groups = new Map<string, FeatureRow>();
  for (const c of cases) {
    const id = c.source_path == null ? "manual" : JSON.stringify([c.feature_name, c.source_path]);
    let g = groups.get(id);
    if (!g) {
      g = { feature_name: c.source_path == null ? null : c.feature_name, path: c.source_path, folder: folderOf(c.source_path),
        case_count: 0, case_numbers: [], has_source: false, cases: [] };
      groups.set(id, g);
    }
    g.case_count += 1;
    g.case_numbers.push(c.number);
    g.cases!.push(c);
  }
  const key = (g: FeatureRow) => [g.path == null ? 1 : 0, g.folder ?? "", (g.feature_name ?? "").toLowerCase(), g.path ?? ""] as const;
  return [...groups.values()].sort((a, b) => {
    const [ka, kb] = [key(a), key(b)];
    for (let i = 0; i < ka.length; i++) if (ka[i] !== kb[i]) return ka[i] < kb[i] ? -1 : 1;
    return 0;
  });
}
