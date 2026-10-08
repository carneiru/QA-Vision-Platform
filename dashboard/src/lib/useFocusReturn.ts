import { useEffect, useRef } from "react";

/** A ref for the control that opened something (a form, a panel). When `open` turns false again, focus goes back to it,
 *  so closing by Cancel, Escape or a successful submit never leaves focus on a button that is gone. */
export function useFocusReturn<T extends HTMLElement>(open: boolean) {
  const ref = useRef<T>(null);
  const wasOpen = useRef(open);
  useEffect(() => {
    if (wasOpen.current && !open) ref.current?.focus();
    wasOpen.current = open;
  }, [open]);
  return ref;
}
