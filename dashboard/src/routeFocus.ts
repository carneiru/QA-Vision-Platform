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

/** On every user navigation (not the first render, not redirects), move focus
 *  to the new view's content so screen readers start there and keyboard users
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
    focusContent();
  }, [pathname, navigationType]);
}
