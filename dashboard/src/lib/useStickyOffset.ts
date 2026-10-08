import { useEffect, useState, type RefObject } from "react";

/** The height of a bar stuck to the bottom of the viewport, kept current, and written to the page's
 *  scroll-padding-bottom while the bar exists: the browser then scrolls a focused control above the bar
 *  instead of under it (WCAG 2.4.11 Focus Not Obscured). Returns the height for padding the content. */
export function useStickyBottomOffset(ref: RefObject<HTMLElement | null>, active: boolean, gap = 8): number {
  const [height, setHeight] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!active || !el) {
      setHeight(0);
      return;
    }
    const measure = () => setHeight(el.offsetHeight);
    measure();
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(measure) : null;
    observer?.observe(el);
    return () => observer?.disconnect();
  }, [ref, active]);
  useEffect(() => {
    if (height <= 0) return;
    const root = document.documentElement;
    const before = root.style.scrollPaddingBottom;
    root.style.scrollPaddingBottom = `${height + gap}px`;
    return () => {
      root.style.scrollPaddingBottom = before;
    };
  }, [height, gap]);
  return height;
}
