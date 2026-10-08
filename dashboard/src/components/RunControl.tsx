import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Play } from "lucide-react";
import { ApiError } from "../api/http";
import { RunSelection, createRunRequest } from "../api/runRequests";
import { estimateText, runEstimate, useDurationEstimate } from "../lib/durationEstimate";
import { useRunGate } from "../lib/useRunGate";
import ErrorBanner from "./ErrorBanner";
import { SkeletonStatus } from "./Skeleton";

const SHOWN = 10;

interface Props {
  projectId: number;
  /** The cases the confirmation lists, in order. A manual case cannot run: a suite run skips it, and the dialog counts it apart. */
  cases: { number: number; title: string; manual?: boolean; testKey?: string | null }[];
  selection: RunSelection;
  /** Visible text of the trigger: "Run", "Run selected (3)", "Run suite". */
  label: string;
  onStarted?: () => void;
  /** Why Play is off when there is nothing to run, e.g. "This suite has no cases". */
  emptyReason?: string;
  /** The view's one primary button, unless another action on it is (a dirty form's Save). Default true. */
  emphasis?: boolean;
}

/** Play: a trigger, the reason it is disabled, and an inline confirmation (no modal, DESIGN.md). */
export default function RunControl({ projectId, cases, selection, label, onStarted, emptyReason, emphasis = true }: Props) {
  const gate = useRunGate(projectId);
  const qc = useQueryClient();
  const ids = useId();
  const [open, setOpen] = useState(false);
  const sending = useRef(false); // a double click must send one request, before React re-renders
  const triggerRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const restoreFocus = useRef(false);
  // The server refused because the world changed (a run is active, the target is gone): say so, outside the closed dialog
  const [notice, setNotice] = useState<string | null>(null);

  const runnable = cases.filter((c) => !c.manual);
  // Asked while the question is open (the selection bar or suite header may have asked already: same key, no new request).
  // It never holds Play back: loading shows a placeholder, a failure shows nothing, and Run sends what is known then.
  const estimate = useDurationEstimate(projectId, runnable.map((c) => c.testKey), { enabled: open });
  // Another selection's answer kept while this one loads is not this selection's estimate
  const known = estimate.isPlaceholderData ? undefined : estimate.data;

  const start = useMutation({
    mutationFn: () => createRunRequest(projectId, selection, runEstimate(known)),
    onSuccess: async () => {
      restoreFocus.current = true; // before the refetch: it may turn the gate off and close the dialog under us
      await qc.invalidateQueries({ queryKey: ["run-requests", projectId] });
      setOpen(false);
      onStarted?.();
    },
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 409 || error.status === 412)) {
        void qc.invalidateQueries({ queryKey: ["ci-target", projectId] });
        void qc.invalidateQueries({ queryKey: ["run-requests", projectId] });
        setNotice(error.detail);
        setOpen(false);
        start.reset();
      }
    },
    onSettled: () => {
      sending.current = false;
    },
  });

  useEffect(() => {
    if (open) cancelRef.current?.focus();
  }, [open]);

  // The gate can turn off while the question is open (someone else started a run): drop it for good
  useEffect(() => {
    if (gate && !gate.ok) setOpen(false);
  }, [gate]);

  // A notice about a changed world never outlives it: it goes when Play works again
  useEffect(() => {
    if (gate?.ok) setNotice(null);
  }, [gate?.ok]);

  // After a start the dialog's Cancel button is gone: hand focus to Play, or to the control itself when Play is now off
  useEffect(() => {
    if (open || !restoreFocus.current) return;
    restoreFocus.current = false;
    const trigger = triggerRef.current;
    (trigger && !trigger.disabled ? trigger : boxRef.current)?.focus();
  }, [open]);

  function close() {
    if (start.isPending) return; // the request is already on its way
    setOpen(false);
    start.reset();
    triggerRef.current?.focus();
  }

  function confirm() {
    if (sending.current) return;
    sending.current = true;
    start.mutate();
  }

  const n = runnable.length;
  const skipped = cases.length - n;
  const blocked = gate === undefined || !gate.ok || n === 0;
  return (
    <div ref={boxRef} tabIndex={-1} className="run-control">
      <button ref={triggerRef} type="button" className={emphasis && !open ? "primary" : undefined} disabled={blocked} onClick={() => { setNotice(null); setOpen(true); }}
        aria-describedby={gate && !gate.ok ? `${ids}-why` : undefined}>
        <Play size={16} aria-hidden="true" /> {label}
      </button>
      {gate && !gate.ok && (
        <span id={`${ids}-why`} className="run-reason">
          {gate.toSettings ? <Link to={`/projects/${projectId}/settings`}>{gate.reason}</Link> : gate.reason}
        </span>
      )}
      {gate?.ok && n === 0 && emptyReason && <span className="run-reason">{emptyReason}</span>}
      {notice != null && !(gate && !gate.ok && gate.reason === notice) && <span className="error-banner" role="alert">{notice}</span>}
      {open && gate?.ok && (
        <div className="card run-confirm" role="dialog" aria-labelledby={`${ids}-title`}
          onKeyDown={(e) => { if (e.key === "Escape") close(); }}>
          <h2 id={`${ids}-title`}>
            {skipped > 0
              ? `Run ${n === 1 ? "1 automated case" : `${n} automated cases`} (${skipped === 1 ? "1 manual case" : `${skipped} manual cases`} skipped)?`
              : n === 1 ? "Run 1 test?" : `Run ${n} tests?`}
          </h2>
          <ul className="run-confirm-cases">
            {runnable.slice(0, SHOWN).map((c) => <li key={c.number}>{`TC-${c.number} · ${c.title}`}</li>)}
          </ul>
          {n > SHOWN && <p className="muted">{`+${n - SHOWN} more`}</p>}
          <p>{`${gate.target.repo} @ ${gate.target.ref}`}</p>
          {known ? (
            <p className="run-estimate">
              {known.estimate_ms === null ? estimateText(known) : `Estimated duration ${estimateText(known)}`}
            </p>
          ) : (estimate.isPending || estimate.isPlaceholderData) && (
            <SkeletonStatus label="Estimating duration" className="run-estimate">
              <span className="skeleton estimate-skeleton" aria-hidden="true" />
            </SkeletonStatus>
          )}
          <p className="note warn-note" role="note">
            <CircleAlert size={16} aria-hidden="true" />
            <span>Tests may create real bookings in staging</span>
          </p>
          {start.error != null && <ErrorBanner error={start.error} />}
          <div className="button-row">
            <button type="button" className="primary" onClick={confirm} disabled={start.isPending}>
              {start.isPending ? "Starting…" : "Run"}
            </button>
            <button ref={cancelRef} type="button" onClick={close} disabled={start.isPending}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
