import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import type { CaseAreas } from "../../api/cases";
import { GROUPINGS, type Grouping, defaultFolderDepth, maxFolderDepth } from "../../lib/reportScope";

/** Sections 3 and 5 share one grouping, kept in the URL (`group`, `depth`) as a view setting: "Clear all" keeps it. */
export function useGrouping(areas?: CaseAreas) {
  const [params, setParams] = useSearchParams();
  const raw = params.get("group") ?? "";
  const grouping: Grouping = (GROUPINGS as string[]).includes(raw) ? (raw as Grouping) : "feature";
  const deepest = areas ? maxFolderDepth(areas) : 1;
  const asked = Number(params.get("depth"));
  const depth = Number.isInteger(asked) && asked >= 1 && asked <= deepest ? asked : areas ? defaultFolderDepth(areas) : 1;
  const set = useCallback((key: string, value: string) => setParams((prev) => {
    const next = new URLSearchParams(prev);
    if (value) next.set(key, value);
    else next.delete(key);
    return next;
  }), [setParams]);
  return {
    grouping,
    depth,
    deepest,
    setGrouping: (g: Grouping) => set("group", g === "feature" ? "" : g),
    setDepth: (d: number) => set("depth", String(d)),
  };
}
