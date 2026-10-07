import { formatDuration } from "../api/analytics";
import { RunRequest } from "../api/runRequests";
import { Run } from "../api/runs";

export type RunTone = "queued" | "running" | "passed" | "failed" | "cancelled" | "error";
export const RESULTS_WAIT_MS = 5 * 60_000;
/** Results are looked up from this long before the request, so clock skew never hides them. */
export const MATCH_SLACK_MS = 10 * 60_000;

/** What a run request's state reads as, in the panel and in the Requested runs tab. */
export function describeRun(r: RunRequest, nameOf: (id: number | null) => string, now: number = Date.now()): { text: string; tone: RunTone } {
  switch (r.status) {
    case "queued":
      return { text: "Queued", tone: "queued" };
    case "running": {
      const tests = r.case_count === 1 ? "1 test" : `${r.case_count} tests`;
      const elapsed = formatDuration(Math.max(0, now - Date.parse(r.requested_at)));
      return { text: `Running · ${tests} · started by ${nameOf(r.requested_by)} · ${elapsed}`, tone: "running" };
    }
    case "cancelling":
      return { text: "Stopping…", tone: "cancelled" };
    case "cancelled":
      return { text: r.stopped_by != null ? `Stopped by ${nameOf(r.stopped_by)}` : "Cancelled", tone: "cancelled" };
    case "failed_to_start":
      return { text: `Didn't start: ${r.error ?? "unknown error"}`, tone: "error" };
    case "completed":
      if (r.conclusion === "success") return { text: "Passed", tone: "passed" };
      if (r.conclusion === "skipped") return { text: "Skipped", tone: "cancelled" };
      return { text: "Failed", tone: "failed" };
  }
}

/** The QA Vision test run this request's GitHub run uploaded: same CI URL, ignoring case
 *  (GitHub may return owner/repo with different capitals). */
export function matchRun(runs: Run[], url: string | null): Run | undefined {
  if (!url) return undefined;
  const wanted = url.toLowerCase();
  return runs.find((r) => r.ci_run_url?.toLowerCase() === wanted);
}
