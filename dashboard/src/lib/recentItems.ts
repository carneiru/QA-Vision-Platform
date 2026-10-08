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

/** One list per signed-in user (`qeos.palette.recent.<user id>`), so a shared browser never shows one account's
 *  items to the next. The bare prefix is an older, unkeyed list; sign-out removes it with the rest. */
const PREFIX = "qeos.palette.recent";
export const MAX_RECENT = 5;

const keyFor = (userId: number) => `${PREFIX}.${userId}`;

function valid(x: unknown): x is RecentItem {
  const r = x as RecentItem;
  return typeof r === "object" && r !== null && typeof r.id === "string" && typeof r.label === "string"
    && typeof r.href === "string" && r.href.startsWith("/") && (r.projectId === null || typeof r.projectId === "number");
}

/** The user's last opened items, newest first. No user yet, blocked or corrupt storage: none. */
export function readRecent(userId: number | undefined): RecentItem[] {
  if (userId === undefined) return [];
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(keyFor(userId)) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(valid).slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
}

/** Puts the item first, drops an earlier copy of it, keeps the last 5. No user yet or blocked storage: not kept. */
export function pushRecent(userId: number | undefined, item: RecentItem): void {
  if (userId === undefined) return;
  const next = [item, ...readRecent(userId).filter((r) => r.href !== item.href)].slice(0, MAX_RECENT);
  try {
    localStorage.setItem(keyFor(userId), JSON.stringify(next));
  } catch {
    // Storage blocked: nothing is remembered
  }
}

/** Sign-out: forgets every user's list on this browser. */
export function clearRecent(): void {
  try {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k === PREFIX || k?.startsWith(`${PREFIX}.`)) keys.push(k);
    }
    keys.forEach((k) => localStorage.removeItem(k));
  } catch {
    // Storage blocked: there is nothing to forget
  }
}
