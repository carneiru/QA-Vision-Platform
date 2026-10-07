import { useEffect, useState } from "react";

/** The current time, re-read every `everyMs` so time-based text (elapsed, "results not received") keeps up with no other re-render.
 *  With `null` it stays idle: no timer runs (nothing on screen depends on the time). */
export function useNow(everyMs: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (everyMs === null) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(id);
  }, [everyMs]);
  return now;
}
