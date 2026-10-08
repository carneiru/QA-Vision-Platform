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
export default function FiltersDisclosure({ id, active, reveal = active, children, detailsRef }: {
  id: string;
  /** How many filters inside are applied (the summary count) */
  active: number;
  /** How many of those only the form shows: these open it. A filter a pressed quick chip already shows does not. */
  reveal?: number;
  children: ReactNode;
  /** The details element, for "+ Filter" to open it (revealFilters) */
  detailsRef?: Ref<HTMLDetailsElement>;
}) {
  const storageKey = `qeos.filters.${id}`;
  // Active filters win over the remembered choice: a link with filters in it must show them
  const [open, setOpen] = useState(() => reveal > 0 || (remembered(storageKey) ?? !isNarrow()));
  const hadActive = useRef(reveal > 0);
  useEffect(() => {
    if (reveal > 0 && !hadActive.current) setOpen(true);
    hadActive.current = reveal > 0;
  }, [reveal]);
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
