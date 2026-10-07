import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Play } from "lucide-react";
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
}

/** Play: a trigger, the reason it is disabled, and an inline confirmation (no modal, DESIGN.md). */
export default function RunControl({ projectId, cases, selection, label, onStarted }: Props) {
  const gate = useRunGate(projectId);
  const qc = useQueryClient();
  const ids = useId();
  const [open, setOpen] = useState(false);
  const sending = useRef(false); // a double click must send one request, before React re-renders
  const triggerRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  const start = useMutation({
    mutationFn: () => createRunRequest(projectId, selection),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["run-requests", projectId] });
      setOpen(false);
      onStarted?.();
    },
    onSettled: () => {
      sending.current = false;
    },
  });

  useEffect(() => {
    if (open) cancelRef.current?.focus();
  }, [open]);

  function close() {
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
    <div className="run-control">
      <button ref={triggerRef} type="button" className="primary" disabled={blocked} onClick={() => setOpen(true)}
        aria-describedby={gate && !gate.ok ? `${ids}-why` : undefined}>
        <Play size={16} aria-hidden="true" /> {label}
      </button>
      {gate && !gate.ok && (
        <span id={`${ids}-why`} className="run-reason">
          {gate.toSettings ? <Link to={`/projects/${projectId}/settings`}>{gate.reason}</Link> : gate.reason}
        </span>
      )}
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
            <button ref={cancelRef} type="button" onClick={close}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
