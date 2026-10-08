import { useEffect, useRef, useState, type ReactNode, type Ref } from "react";
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
 *  remembered for the session, but active filters are never hidden: they open it whatever was remembered. */
export default function FiltersDisclosure({ id, active, children, detailsRef }: {
  id: string;
  active: number;
  children: ReactNode;
  /** The details element, for "+ Filter" to open it (revealFilters) */
  detailsRef?: Ref<HTMLDetailsElement>;
}) {
  const storageKey = `qeos.filters.${id}`;
  // Active filters win over the remembered choice: a link with filters in it must show them
  const [open, setOpen] = useState(() => active > 0 || (remembered(storageKey) ?? !isNarrow()));
  const hadActive = useRef(active > 0);
  useEffect(() => {
    if (active > 0 && !hadActive.current) setOpen(true);
    hadActive.current = active > 0;
  }, [active]);
  return (
    <details
      ref={detailsRef}
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
