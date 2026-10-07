import { useEffect, useState, type ReactNode } from "react";

interface Props {
  /** Names the group for screen readers, e.g. "API key new-ci". */
  label: string;
  /** What Copy puts on the clipboard. */
  value: string;
  /** What the reader sees; defaults to the value itself. */
  display?: ReactNode;
  /** Accessible name of the Copy button (it contains the visible text). */
  copyLabel: string;
  copyText: string;
  note?: string;
}

/** A value the server shows once (API key, invitation link, recovery codes): framed, monospace,
 *  wraps anywhere, with a Copy button whose result is announced politely. */
export default function SecretBlock({
  label, value, display, copyLabel, copyText,
  note = "This is shown once. Copy it now: it cannot be shown again.",
}: Props) {
  const [message, setMessage] = useState("");
  useEffect(() => setMessage(""), [value]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setMessage("Copied");
    } catch {
      setMessage("Could not copy. Select the text and copy it by hand.");
    }
  }

  return (
    <div className="secret-block" role="group" aria-label={label}>
      <p className="secret-note">{note}</p>
      <div className="secret-frame">
        {display ?? <code className="secret-value">{value}</code>}
        <button type="button" aria-label={copyLabel} onClick={copy}>
          {message === "Copied" ? "Copied" : copyText}
        </button>
      </div>
      <span role="status" aria-live="polite" className="sr-only">{message}</span>
    </div>
  );
}
