import { getFlaky, getTrends } from "../api/analytics";

/** The Flaky view's default thresholds: the Overview card and the Cases tile count the same tests it lists. */
export const FLAKY_DEFAULTS = { windowDays: 14, minRuns: 5, minFlipRate: 0.3 } as const;

/** Project health figures are re-asked at most once a minute (a new upload invalidates them on Overview). */
const HEALTH_STALE_MS = 60_000;

/** The flaky tests at the default thresholds, quarantined ones included (`muted`), so a reader can count both.
 *  Overview and the Cases tile share it. */
export const flakyHealthQuery = (projectId: number) => ({
  queryKey: ["flaky", projectId, "health"] as const,
  queryFn: () => getFlaky(projectId, { ...FLAKY_DEFAULTS, includeMuted: true }),
  staleTime: HEALTH_STALE_MS,
});

/** This week's and last week's pass rate (two weekly buckets). Overview and the Cases tile share it. */
export const passRateWeeksQuery = (projectId: number, tz: string) => ({
  queryKey: ["trends", projectId, "overview-weeks", tz] as const,
  queryFn: () => getTrends(projectId, { days: 14, tz, bucket: "week" }),
  staleTime: HEALTH_STALE_MS,
});
