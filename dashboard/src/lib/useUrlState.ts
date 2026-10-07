import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

/** The value when it is one of the allowed ones, else the fallback: a hand-edited URL never reaches the API. */
export function oneOf<T extends string>(value: string, allowed: readonly T[], fallback: T): T {
  return (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
}

/** The page start in `offset`, snapped to a page boundary; junk reads as page 1. */
export function pageOffset(params: URLSearchParams, pageSize: number): number {
  const raw = Number(params.get("offset"));
  return Number.isInteger(raw) && raw > 0 ? Math.floor(raw / pageSize) * pageSize : 0;
}

/** A copy of the params with `offset` set (0 removes it). */
export function withOffset(params: URLSearchParams, to: number): URLSearchParams {
  const next = new URLSearchParams(params);
  if (to > 0) next.set("offset", String(to));
  else next.delete("offset");
  return next;
}

/**
 * Filters, sort and paging kept in the query string, so reload, share and
 * Back/Forward restore the view. Values equal to their default are not
 * written; any filter change drops `offset` (back to page 1).
 * `defaults` must be a stable (module-level) object.
 */
export function useUrlState<K extends string>(defaults: Readonly<Record<K, string>>, pageSize: number) {
  const [params, setParams] = useSearchParams();
  const values = {} as Record<K, string>;
  for (const key of Object.keys(defaults) as K[]) values[key] = params.get(key) ?? defaults[key];
  const offset = pageOffset(params, pageSize);

  /** Sets filter values (resetting the page). `replace` is for per-keystroke inputs, so Back is not flooded. */
  const update = useCallback(
    (patch: Partial<Record<K, string>>, options?: { replace?: boolean }) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(patch) as [K, string | undefined][]) {
            if (value === undefined || value === "" || value === defaults[key]) next.delete(key);
            else next.set(key, value);
          }
          next.delete("offset");
          return next;
        },
        { replace: options?.replace },
      );
    },
    [setParams, defaults],
  );

  const setOffset = useCallback(
    (to: number) => {
      setParams((prev) => withOffset(prev, to));
    },
    [setParams],
  );

  return { values, offset, update, setOffset };
}

/**
 * A text box's draft: it follows the URL value (Back, pasted link) but is only written to it on submit.
 * `commit(normalize)` is the submit step: it rewrites the draft to its normalized form (trimmed, clamped) and
 * returns that for the URL. The effect alone would miss the case where normalizing lands on the value the URL
 * already has, which would leave the box showing text the page is not using.
 */
export function useDraft(value: string) {
  const [draft, setDraft] = useState(value);
  const latest = useRef(draft);
  latest.current = draft;
  useEffect(() => setDraft(value), [value]);
  const commit = useCallback((normalize: (raw: string) => string = (raw) => raw) => {
    const normalized = normalize(latest.current);
    setDraft(normalized);
    return normalized;
  }, []);
  return [draft, setDraft, commit] as const;
}
