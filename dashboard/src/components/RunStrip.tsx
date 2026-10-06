import { Link } from "react-router-dom";

export type StripStatus = "passed" | "failed" | "rerun" | "skipped" | null;
export interface StripRun { id: number; started_at: string; branch: string | null }

const WORD: Record<"passed" | "failed" | "rerun" | "skipped" | "none", string> = {
  passed: "passed",
  failed: "failed",
  rerun: "re-run",
  skipped: "skipped",
  none: "not run",
};
const ORDER = ["passed", "failed", "rerun", "skipped", "none"] as const;

const dateFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export function stripSummary(statuses: StripStatus[]): string {
  const parts = ORDER.flatMap((k) => {
    const n = statuses.filter((s) => (s ?? "none") === k).length;
    return n > 0 ? [`${n} ${WORD[k]}`] : [];
  });
  return `Last ${statuses.length} runs: ${parts.join(", ")}`;
}

export default function RunStrip({ projectId, runs, statuses }: { projectId: number; runs: StripRun[]; statuses: StripStatus[] }) {
  return (
    <div className="run-strip" role="group" aria-label={stripSummary(statuses)}>
      {runs.map((run, i) => {
        const key = statuses[i] ?? "none";
        const label = `Run #${run.id}, ${dateFormat.format(new Date(run.started_at))}: ${WORD[key]}`;
        return (
          <Link key={run.id} className={`run-bar bar-${key}`} to={`/projects/${projectId}/runs/${run.id}`} aria-label={label} title={label} />
        );
      })}
    </div>
  );
}

export function RunStripSkeleton() {
  return (
    <div className="run-strip">
      {Array.from({ length: 10 }, (_, i) => <span key={i} className="run-bar bar-loading" aria-hidden="true" />)}
      <span className="sr-only">Loading last runs</span>
    </div>
  );
}
