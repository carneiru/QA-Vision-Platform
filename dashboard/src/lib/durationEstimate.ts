import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { type DurationEstimate, getDurationEstimate } from "../api/analytics";
import { MAX_RUN_CASES, type RunEstimate, type RunRequest } from "../api/runRequests";
import { endedAt } from "./runStatus";

const MINUTE = 60_000;
/** The live total in the selection bar waits this long after the last tick before asking. */
export const ESTIMATE_DEBOUNCE_MS = 400;

/** "under 1 min", "12 min" (1 to 90 minutes), "1 h 40 min". */
export function formatMinutes(ms: number): string {
  if (ms < MINUTE) return "under 1 min";
  const minutes = Math.round(ms / MINUTE);
  if (minutes <= 90) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

/** "≈ 6 min"; under a minute reads plainly "under 1 min". */
export function approxDuration(ms: number): string {
  const text = formatMinutes(ms);
  return ms < MINUTE ? text : `≈ ${text}`;
}

/** "≈ 12 min (up to 15 min) · 3 tests without history", or "No history to estimate yet". */
export function estimateText(e: DurationEstimate): string {
  if (e.estimate_ms === null) return "No history to estimate yet";
  let text = approxDuration(e.estimate_ms);
  if (e.upper_ms !== null && formatMinutes(e.upper_ms) !== formatMinutes(e.estimate_ms)) text += ` (up to ${formatMinutes(e.upper_ms)})`;
  const n = e.tests_without_history;
  if (n > 0) text += ` · ${n === 1 ? "1 test" : `${n} tests`} without history`;
  return text;
}

/** Test-management refuses an estimate over a day (422): such a value is left out rather than block Play. */
export const MAX_STORED_ESTIMATE_MS = 86_400_000;

/** What createRunRequest stores, or null when nothing could be estimated (or it is beyond what can be stored). */
export function runEstimate(e: DurationEstimate | undefined): RunEstimate | null {
  if (!e || e.estimate_ms === null || e.upper_ms === null) return null;
  if (e.estimate_ms > MAX_STORED_ESTIMATE_MS || e.upper_ms > MAX_STORED_ESTIMATE_MS) return null;
  return { estimate_ms: e.estimate_ms, estimate_upper_ms: e.upper_ms };
}

/** Requested runs: "≈ 4 min left" or "running longer than estimated" while running, "estimated 12 min · took 14 min" once
 *  completed; null for a request without an estimate or in any other state. Counted from requested_at (the request has no
 *  start time of its own), ended at endedAt (when the end was seen). */
export function requestTiming(r: RunRequest, now: number): string | null {
  if (r.estimate_ms === null) return null;
  const requested = Date.parse(r.requested_at);
  if (r.status === "running") {
    const left = requested + r.estimate_ms - now;
    if (left <= 0) return "running longer than estimated";
    return left < MINUTE ? "under 1 min left" : `≈ ${formatMinutes(left)} left`;
  }
  if (r.status === "completed") {
    return `estimated ${formatMinutes(r.estimate_ms)} · took ${formatMinutes(Math.max(0, endedAt(r) - requested))}`;
  }
  return null;
}

function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    if (ms <= 0) {
      setSettled(value);
      return;
    }
    const id = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return ms <= 0 ? value : settled;
}

/** The duration estimate for these test keys (nulls and duplicates dropped, order ignored). Off with no key or more than
 *  a run takes. Keyed by the sorted keys, so the dialog reuses what the selection bar asked; the previous answer stays
 *  while the next loads, so the text never flickers. */
export function useDurationEstimate(projectId: number, keys: (string | null | undefined)[], opts: { debounceMs?: number; enabled?: boolean } = {}) {
  const joined = useMemo(
    () => [...new Set(keys.flatMap((k) => (k ? [k.toLowerCase()] : [])))].sort().join(","),
    [keys],
  );
  const settled = useDebounced(joined, opts.debounceMs ?? 0);
  const sorted = settled === "" ? [] : settled.split(",");
  const enabled = (opts.enabled ?? true) && sorted.length > 0 && sorted.length <= MAX_RUN_CASES;
  const query = useQuery({
    queryKey: ["duration-estimate", projectId, settled],
    queryFn: () => getDurationEstimate(projectId, sorted),
    enabled,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
  // A selection emptied (or over the cap) shows nothing rather than its last answer; while the debounce runs, the last answer stays
  // isPlaceholderData: `data` is still the previous keys' answer (the Play dialog must not store it for these keys)
  return { data: enabled ? query.data : undefined, isPending: enabled && query.isPending, isPlaceholderData: enabled && query.isPlaceholderData };
}
