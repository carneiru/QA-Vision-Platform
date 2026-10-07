import { useContext, useEffect, useRef } from "react";
import { UNSAFE_DataRouterContext, useBlocker } from "react-router-dom";

/** Leaving a page with unsaved edits: the browser asks on reload or close, and the
 *  router asks in place on in-app navigation. Needs a data router for the in-app part;
 *  under a plain router only the browser guard is active. */
export default function UnsavedGuard({ dirty }: { dirty: boolean }) {
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const inDataRouter = useContext(UNSAFE_DataRouterContext) != null;
  return inDataRouter ? <LeaveGuard dirty={dirty} /> : null;
}

function LeaveGuard({ dirty }: { dirty: boolean }) {
  // Read through a ref so a navigation started in the same tick as a successful save is not blocked
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) => dirtyRef.current && currentLocation.pathname !== nextLocation.pathname,
  );
  const stayRef = useRef<HTMLButtonElement>(null);
  const blocked = blocker.state === "blocked";
  useEffect(() => {
    if (blocked) stayRef.current?.focus();
  }, [blocked]);

  if (blocker.state !== "blocked") return null;
  return (
    <div
      className="error-banner"
      role="alertdialog"
      aria-label="Unsaved changes"
      onKeyDown={(e) => {
        if (e.key === "Escape") blocker.reset();
      }}
    >
      <span>You have unsaved changes. Leave without saving them?</span>
      <button type="button" ref={stayRef} onClick={() => blocker.reset()}>Stay</button>
      <button type="button" className="danger" onClick={() => blocker.proceed()}>Leave without saving</button>
    </div>
  );
}
