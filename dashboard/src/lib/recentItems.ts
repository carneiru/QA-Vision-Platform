/** What the command palette remembers of an opened result: enough to show it again and open it. */
export interface RecentItem {
  id: string;
  kind: "page" | "case" | "test" | "run" | "project";
  label: string;
  detail?: string;
  href: string;
  /** The project the item lives in; null for workspace pages and projects themselves. */
  projectId: number | null;
}

const KEY = "qeos.palette.recent";
export const MAX_RECENT = 5;

function valid(x: unknown): x is RecentItem {
  const r = x as RecentItem;
  return typeof r === "object" && r !== null && typeof r.id === "string" && typeof r.label === "string"
    && typeof r.href === "string" && r.href.startsWith("/") && (r.projectId === null || typeof r.projectId === "number");
}

/** The last opened items, newest first. Blocked or corrupt storage reads as none. */
export function readRecent(): RecentItem[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(valid).slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
}

/** Puts the item first, drops an earlier copy of it, keeps the last 5. Blocked storage forgets it. */
export function pushRecent(item: RecentItem): void {
  const next = [item, ...readRecent().filter((r) => r.href !== item.href)].slice(0, MAX_RECENT);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Storage blocked: nothing is remembered
  }
}
