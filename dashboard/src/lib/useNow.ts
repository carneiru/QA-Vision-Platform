import { useEffect, useState } from "react";

/** The current time, re-read every `everyMs` so time-based text (elapsed, "results not received") keeps up with no other re-render. */
export function useNow(everyMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(id);
  }, [everyMs]);
  return now;
}
