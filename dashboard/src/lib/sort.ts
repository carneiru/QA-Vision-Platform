export type SortDir = "asc" | "desc";
export interface SortState<K extends string = string> {
  key: K;
  dir: SortDir;
}

/** The sort in the URL (`sort`, `dir`), or the fallback when either is missing or hand-edited to junk. */
export function parseSort<K extends string>(
  sort: string | null | undefined,
  dir: string | null | undefined,
  keys: readonly K[],
  fallback: SortState<K>,
): SortState<K> {
  const key = (keys as readonly string[]).includes(sort ?? "") ? (sort as K) : fallback.key;
  if (dir === "asc" || dir === "desc") return { key, dir };
  return { key, dir: key === fallback.key ? fallback.dir : "asc" };
}

/** Clicking the sorted column flips it; clicking another starts it in `firstDir` (text ascending, figures descending). */
export function nextSort<K extends string>(current: SortState<K>, key: K, firstDir: SortDir): SortState<K> {
  if (current.key === key) return { key, dir: current.dir === "asc" ? "desc" : "asc" };
  return { key, dir: firstDir };
}

/** A sorted copy. Missing values (null) sort last in either direction; ties keep their loaded order. */
export function sortRows<T, K extends string>(
  rows: readonly T[],
  sort: SortState<K>,
  get: (row: T, key: K) => string | number | null | undefined,
): T[] {
  const sign = sort.dir === "asc" ? 1 : -1;
  return rows
    .map((row, index) => ({ row, index, value: get(row, sort.key) }))
    .sort((a, b) => {
      const aNone = a.value === null || a.value === undefined;
      const bNone = b.value === null || b.value === undefined;
      if (aNone || bNone) return aNone === bNone ? a.index - b.index : aNone ? 1 : -1;
      const cmp =
        typeof a.value === "number" && typeof b.value === "number"
          ? a.value - b.value
          : String(a.value).localeCompare(String(b.value), undefined, { numeric: true, sensitivity: "base" });
      return cmp * sign || a.index - b.index;
    })
    .map((e) => e.row);
}

/** The `sort`/`dir` URL values for a choice: both blank when it is the default, so the default view has a clean URL. */
export function sortPatch<K extends string>(next: SortState<K>, fallback: SortState<K> | null): { sort: string; dir: string } {
  if (fallback && next.key === fallback.key && next.dir === fallback.dir) return { sort: "", dir: "" };
  return { sort: next.key, dir: next.dir };
}
