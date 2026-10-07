import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

export type RunVerdict = "passed" | "failed" | "errored";

/** A run's verdict: failures first, then errors, else passed. */
export function runVerdict(r: { failed: number; errored: number }): RunVerdict {
  return r.failed > 0 ? "failed" : r.errored > 0 ? "errored" : "passed";
}

const VIEW = {
  passed: { label: "Passed", className: "badge badge-passed", Icon: CheckCircle2 },
  failed: { label: "Failed", className: "badge badge-failed", Icon: XCircle },
  errored: { label: "Errored", className: "badge badge-warn", Icon: AlertTriangle },
} as const;

/** Icon and word, so the verdict never rests on colour. `note` extends the word ("· 2 quarantined"). */
export default function RunStatusBadge({ verdict, note }: { verdict: RunVerdict; note?: string }) {
  const { label, className, Icon } = VIEW[verdict];
  return (
    <span className={className}>
      <Icon size={14} aria-hidden="true" /> {label}
      {note ? ` · ${note}` : ""}
    </span>
  );
}
