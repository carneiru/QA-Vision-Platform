import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, CircleSlash, CircleX, Clock, ExternalLink, LoaderCircle } from "lucide-react";
import { ApiError } from "../api/http";
import { getProject } from "../api/orgs";
import { listRuns } from "../api/runs";
import { isActive, stopRunRequest } from "../api/runRequests";
import { MANAGE_ROLES, RUN_ROLES, useCiTarget, useLatestRunRequest } from "../lib/useRunGate";
import { MATCH_SLACK_MS, RESULTS_WAIT_MS, RunTone, describeRun, matchRun } from "../lib/runStatus";
import { useNow } from "../lib/useNow";
import { useUserNames } from "../lib/useUserNames";
import { ExpiryWarning } from "./CiTargetCard";
import ConfirmButton from "./ConfirmButton";
import ErrorBanner from "./ErrorBanner";

const RECENT_MS = 60 * 60_000;
const RESULTS_POLL_MS = 10_000;
const TICK_MS = 30_000;
const ICONS: Record<RunTone, typeof Clock> = {
  queued: Clock, running: LoaderCircle, passed: CheckCircle2, failed: CircleX, cancelled: CircleSlash, error: CircleAlert,
};

interface Props {
  projectId: number;
  /** On a case detail: show only while this case is in the active request. */
  caseNumber?: number;
}

/** The newest run requested from QA Vision: its state, View in GitHub, Stop, then its results. */
export default function RunPanel({ projectId, caseNumber }: Props) {
  const qc = useQueryClient();
  const latest = useLatestRunRequest(projectId);
  const target = useCiTarget(projectId);
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => getProject(projectId) });
  const nameOf = useUserNames(projectId);
  const now = useNow(TICK_MS);
  const r = latest.data ?? null;
  const rid = r?.id;
  const requestedAt = r?.requested_at;
  const runUrl = r?.github_run_url ?? null;
  const ended = r != null && !isActive(r);
  const finishedAt = r?.checked_at ? Date.parse(r.checked_at) : null;
  const waitedTooLong = finishedAt !== null && now - finishedAt > RESULTS_WAIT_MS;
  // Only a run that finished on GitHub uploads results; stopped, cancelled and unstarted ones do not
  const expectsResults = r?.status === "completed" && runUrl != null;
  const results = useQuery({
    queryKey: ["run-requests", projectId, "results", rid],
    queryFn: async () => {
      if (requestedAt === undefined) return null;
      const since = new Date(Date.parse(requestedAt) - MATCH_SLACK_MS).toISOString();
      return matchRun(await listRuns(projectId, { limit: 20, offset: 0, since }), runUrl) ?? null;
    },
    enabled: ended && expectsResults,
    refetchInterval: (q) => (q.state.data || waitedTooLong ? false : RESULTS_POLL_MS),
  });
  const stop = useMutation({
    mutationFn: () => stopRunRequest(projectId, rid as number),
    onSuccess: (updated) => qc.setQueryData(["run-requests", projectId, "latest"], updated),
    onError: (error) => {
      // 409: the run finished first. Show its final state, not an error
      if (error instanceof ApiError && error.status === 409) {
        void qc.invalidateQueries({ queryKey: ["run-requests", projectId] });
        stop.reset();
      }
    },
  });

  const role = project.data?.my_role ?? "";
  const warning = MANAGE_ROLES.includes(role) && target.data ? <ExpiryWarning target={target.data} /> : null;
  const live = r != null && (isActive(r) || r.refreshing);
  const visible = r != null && (caseNumber === undefined
    ? live || now - Date.parse(r.requested_at) < RECENT_MS
    : live && r.selection.some((s) => s.case_number === caseNumber));
  if (!visible || r == null) return caseNumber === undefined ? warning : null;

  const described = describeRun(r, nameOf, now);
  const stopping = stop.isPending;
  const text = stopping ? "Stopping…" : described.text;
  const Icon = ICONS[described.tone];
  const canStop = RUN_ROLES.includes(role) && (r.status === "queued" || r.status === "running");
  return (
    <>
      {warning}
      <section className={`card run-panel run-tone-${described.tone}`} role="status" aria-label="Run from QA Vision">
        <p className="run-panel-state">
          <Icon size={18} aria-hidden="true" />
          <span>{text}</span>
        </p>
        <div className="run-panel-actions">
          {r.github_run_url && (
            <a href={r.github_run_url} target="_blank" rel="noopener noreferrer" className="link-arrow">
              View in GitHub <ExternalLink size={13} aria-hidden="true" />
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          )}
          {canStop && (
            <ConfirmButton label="Stop" ariaLabel="Stop the run" question="Stop this run?" confirmLabel="Stop run"
              onConfirm={() => stop.mutate()} disabled={stopping} />
          )}
        </div>
        {ended && expectsResults && (
          results.data ? (
            <p><Link to={`/projects/${projectId}/runs/${results.data.id}`}>{`Open the results (run #${results.data.id})`}</Link></p>
          ) : waitedTooLong ? (
            <p className="muted">Results not received: check the QA Vision upload step</p>
          ) : (
            <p className="muted">Waiting for results…</p>
          )
        )}
        {stop.error != null && <ErrorBanner error={stop.error} />}
      </section>
    </>
  );
}
