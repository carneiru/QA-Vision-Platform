import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Play } from "lucide-react";
import { ApiError } from "../api/http";
import { RunSelection, createRunRequest } from "../api/runRequests";
import { useRunGate } from "../lib/useRunGate";
import ErrorBanner from "./ErrorBanner";

const SHOWN = 10;

interface Props {
  projectId: number;
  /** The cases the confirmation lists, in order. */
  cases: { number: number; title: string }[];
  selection: RunSelection;
  /** Visible text of the trigger: "Run", "Run selected (3)", "Run suite". */
  label: string;
  onStarted?: () => void;
  /** Why Play is off when there is nothing to run, e.g. "This suite has no cases". */
  emptyReason?: string;
}

/** Play: a trigger, the reason it is disabled, and an inline confirmation (no modal, DESIGN.md). */
export default function RunControl({ projectId, cases, selection, label, onStarted, emptyReason }: Props) {
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

  const start = useMutation({
    mutationFn: () => createRunRequest(projectId, selection),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["run-requests", projectId] });
      restoreFocus.current = true;
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

  const n = cases.length;
  const blocked = gate === undefined || !gate.ok || n === 0;
  return (
    <div ref={boxRef} tabIndex={-1} className="run-control">
      <button ref={triggerRef} type="button" className="primary" disabled={blocked} onClick={() => { setNotice(null); setOpen(true); }}
        aria-describedby={gate && !gate.ok ? `${ids}-why` : undefined}>
        <Play size={16} aria-hidden="true" /> {label}
      </button>
      {gate && !gate.ok && (
        <span id={`${ids}-why`} className="run-reason">
          {gate.toSettings ? <Link to={`/projects/${projectId}/settings`}>{gate.reason}</Link> : gate.reason}
        </span>
      )}
      {gate?.ok && n === 0 && emptyReason && <span className="run-reason">{emptyReason}</span>}
      {notice != null && <span className="error-banner" role="alert">{notice}</span>}
      {open && gate?.ok && (
        <div className="card run-confirm" role="dialog" aria-labelledby={`${ids}-title`}
          onKeyDown={(e) => { if (e.key === "Escape") close(); }}>
          <h3 id={`${ids}-title`}>{n === 1 ? "Run 1 test?" : `Run ${n} tests?`}</h3>
          <ul className="run-confirm-cases">
            {cases.slice(0, SHOWN).map((c) => <li key={c.number}>{`TC-${c.number} · ${c.title}`}</li>)}
          </ul>
          {n > SHOWN && <p className="muted">{`+${n - SHOWN} more`}</p>}
          <p>{`${gate.target.repo} @ ${gate.target.ref}`}</p>
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
