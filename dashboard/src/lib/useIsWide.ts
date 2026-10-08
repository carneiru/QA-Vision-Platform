import { useCallback, useEffect, useState } from "react";

/**
 * Whether a table card's content is wider than the card (scrollWidth > clientWidth), kept current with a
 * ResizeObserver on the card and its table (a narrower window, new rows). A wide card keeps its sideways
 * scroll; only a card that fits gets the sticky header (`.is-wide` in index.css).
 * Returns a callback ref, so a card that mounts later (after its data) is still observed.
 */
export function useIsWide<T extends HTMLElement>() {
  const [el, setEl] = useState<T | null>(null);
  const [wide, setWide] = useState(false);
  const ref = useCallback((node: T | null) => setEl(node), []);
  useEffect(() => {
    if (!el) return;
    const measure = () => setWide(el.scrollWidth > el.clientWidth);
    measure();
    if (typeof ResizeObserver !== "function") return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    const table = el.querySelector("table");
    if (table) observer.observe(table);
    return () => observer.disconnect();
  }, [el]);
  return { ref, wide };
}

/** The class of a list's table card: it may stick its header only while its table fits. */
export const tableCardClass = (wide: boolean) => (wide ? "card sticky-head is-wide" : "card sticky-head");
