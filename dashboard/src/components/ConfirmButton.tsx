import { useEffect, useRef, useState } from "react";

interface Props {
  /** Visible text of the trigger, e.g. "Revoke". */
  label: string;
  /** Accessible name of the trigger when the row needs naming, e.g. "Revoke key ci". */
  ariaLabel?: string;
  /** The consequence, in one sentence: what stops working. */
  question: string;
  confirmLabel: string;
  onConfirm: () => void;
  disabled?: boolean;
}

/** A destructive action that asks in place before acting. The confirm button
 *  takes focus; Cancel and Escape back out and return focus to the trigger. */
export default function ConfirmButton({ label, ariaLabel, question, confirmLabel, onConfirm, disabled }: Props) {
  const [asking, setAsking] = useState(false);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef(false);

  useEffect(() => {
    if (asking) confirmRef.current?.focus();
    else if (returnFocus.current) {
      returnFocus.current = false;
      triggerRef.current?.focus();
    }
  }, [asking]);

  function cancel() {
    returnFocus.current = true;
    setAsking(false);
  }

  if (!asking) {
    return (
      <button ref={triggerRef} aria-label={ariaLabel} onClick={() => setAsking(true)} disabled={disabled}>
        {label}
      </button>
    );
  }
  return (
    <span
      className="confirm"
      role="group"
      aria-label={question}
      onKeyDown={(e) => {
        if (e.key === "Escape") cancel();
      }}
    >
      <span>{question}</span>
      <button
        ref={confirmRef}
        className="danger"
        onClick={() => {
          setAsking(false);
          onConfirm();
        }}
      >
        {confirmLabel}
      </button>
      <button onClick={cancel}>Cancel</button>
    </span>
  );
}
