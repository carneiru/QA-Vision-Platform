/** How often views that show the newest runs poll for more. Results arrive
 *  when a CI job ends, so seconds-level push would add little (ADR-021).
 *  TanStack Query pauses the interval while the tab is hidden. */
export const LIVE_REFRESH_MS = 30_000;
