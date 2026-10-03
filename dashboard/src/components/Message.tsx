import { useState } from "react";

/** First line with an expander for multi-line failure messages. */
export default function Message({ text }: { text: string | null }) {
  const [open, setOpen] = useState(false);
  if (!text) return <span className="muted">—</span>;
  const firstLine = text.split("\n")[0];
  if (text === firstLine) return <span>{text}</span>;
  return open ? (
    <pre className="message-full">{text}</pre>
  ) : (
    <span>
      {firstLine}{" "}
      <button onClick={() => setOpen(true)}>Show full message</button>
    </span>
  );
}
