import { useEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

const APP_NAME = "QEOS";

export function pageTitle(...parts: string[]): string {
  return [...parts, APP_NAME].join(" · ");
}

/** The current view's content: a project's tab panel when there is one, else <main>. */
export function focusContent(): void {
  (document.getElementById("content") ?? document.getElementById("main"))?.focus();
}

/** The page's h1 when it has rendered one (PageHeader gives it tabIndex -1), else the content region.
 *  Screen readers then start on the page name, and Tab continues from the top of the page. */
export function focusPageHeading(): void {
  const region = document.getElementById("content") ?? document.getElementById("main");
  const h1 = region?.querySelector<HTMLElement>("h1");
  if (h1) {
    if (!h1.hasAttribute("tabindex")) h1.tabIndex = -1;
    h1.focus();
  } else region?.focus();
}

/** On every user navigation (not the first render, not redirects), move focus
 *  to the new view's heading so screen readers start there and keyboard users
 *  do not have to tab back through the header. */
export function useFocusOnNavigate(): void {
  const { pathname } = useLocation();
  const navigationType = useNavigationType();
  // Compared by value, not a first-run flag: StrictMode runs mount effects twice
  const previous = useRef(pathname);
  useEffect(() => {
    if (previous.current === pathname) return;
    previous.current = pathname;
    if (navigationType === "REPLACE") return;
    focusPageHeading();
  }, [pathname, navigationType]);
}
