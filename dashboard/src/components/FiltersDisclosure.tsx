import { useState, type ReactNode } from "react";
import { ChevronRight } from "lucide-react";

const NARROW_QUERY = "(max-width: 640px)";

function isNarrow(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(NARROW_QUERY).matches;
}

function remembered(key: string): boolean | null {
  try {
    const v = sessionStorage.getItem(key);
    return v === "open" ? true : v === "closed" ? false : null;
  } catch {
    return null;
  }
}

/** The secondary filters of a list, behind a "Filters (n active)" summary. Open on wide screens;
 *  closed on phones, where ten fields would fill the first screen. A reader's own choice is
 *  remembered for the session, and active filters are never hidden: they open it. */
export default function FiltersDisclosure({ id, active, children }: { id: string; active: number; children: ReactNode }) {
  const storageKey = `qeos.filters.${id}`;
  const [open, setOpen] = useState(() => remembered(storageKey) ?? (!isNarrow() || active > 0));
  return (
    <details
      className="more-filters"
      open={open}
      onToggle={(e) => {
        const now = (e.currentTarget as HTMLDetailsElement).open;
        if (now === open) return; // the browser also fires toggle when the page sets the attribute
        setOpen(now);
        try { sessionStorage.setItem(storageKey, now ? "open" : "closed"); } catch { /* storage is optional */ }
      }}
    >
      <summary>
        <ChevronRight size={14} aria-hidden="true" className="chevron" />
        {active > 0 ? `Filters (${active} active)` : "Filters"}
      </summary>
      <div className="filters">{children}</div>
    </details>
  );
}
