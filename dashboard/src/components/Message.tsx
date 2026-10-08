import { useId, useState } from "react";

/** First line, with a toggle for multi-line failure messages. The toggle stays where it is (it only changes
 *  what it says), so focus is never lost and a screen reader hears whether the message is open. */
export default function Message({ text, name }: { text: string | null; name?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  if (!text) return <span className="muted">—</span>;
  const firstLine = text.split("\n")[0];
  if (text === firstLine) return <span>{text}</span>;
  return (
    <>
      <span>
        {firstLine}{" "}
        <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
          {open ? "Hide full message" : "Show full message"}
          {name && <span className="sr-only"> for {name}</span>}
        </button>
      </span>
      <pre id={id} className="message-full" hidden={!open}>{text}</pre>
    </>
  );
}
