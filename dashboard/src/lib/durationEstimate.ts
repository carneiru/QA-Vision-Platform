import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { type DurationEstimate, getDurationEstimate } from "../api/analytics";
import { MAX_RUN_CASES, type RunEstimate, type RunRequest } from "../api/runRequests";
import type { Run } from "../api/runs";
import { seenEndAt } from "./runStatus";

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

/** How long the run took: the matched QEOS run's own duration (or its finished_at − started_at); unmatched, from requested_at
 *  to when test-management saw the end; null with no real end time. */
function tookMs(r: RunRequest, run?: Pick<Run, "duration_ms" | "started_at" | "finished_at">): number | null {
  if (run) {
    if (run.duration_ms > 0) return run.duration_ms;
    const span = Date.parse(run.finished_at) - Date.parse(run.started_at);
    if (!Number.isNaN(span)) return Math.max(0, span);
  }
  const seen = seenEndAt(r);
  return seen === null ? null : Math.max(0, seen - Date.parse(r.requested_at));
}

/** Requested runs: "≈ 4 min left" or "running longer than estimated" while running (counted from requested_at: the request
 *  has no start time of its own), "estimated 12 min · took 14 min" once completed (see tookMs; "estimated 12 min" alone with
 *  no end time); null for a request without an estimate or in any other state. */
export function requestTiming(r: RunRequest, now: number, run?: Pick<Run, "duration_ms" | "started_at" | "finished_at">): string | null {
  if (r.estimate_ms === null) return null;
  const requested = Date.parse(r.requested_at);
  if (r.status === "running") {
    const left = requested + r.estimate_ms - now;
    if (left <= 0) return "running longer than estimated";
    return left < MINUTE ? "under 1 min left" : `≈ ${formatMinutes(left)} left`;
  }
  if (r.status === "completed") {
    const took = tookMs(r, run);
    const estimated = `estimated ${formatMinutes(r.estimate_ms)}`;
    return took === null ? estimated : `${estimated} · took ${formatMinutes(took)}`;
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

/** The duration estimate for these cases' test keys (duplicates dropped, order ignored). A case with no linked test (a null
 *  key) is never sent, but counts in `tests_without_history`. Off with no linked key or more than a run takes. Keyed by the sorted keys, so the dialog reuses what the selection bar asked; the previous answer stays
 *  while the next loads, so the text never flickers. */
export function useDurationEstimate(projectId: number, keys: (string | null | undefined)[], opts: { debounceMs?: number; enabled?: boolean } = {}) {
  const joined = useMemo(
    () => [...new Set(keys.flatMap((k) => (k ? [k.toLowerCase()] : [])))].sort().join(","),
    [keys],
  );
  const unlinked = keys.filter((k) => !k).length;
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
  const data = enabled && query.data
    ? (unlinked > 0 ? { ...query.data, tests_without_history: query.data.tests_without_history + unlinked } : query.data)
    : undefined;
  return { data, isPending: enabled && query.isPending, isPlaceholderData: enabled && query.isPlaceholderData };
}
