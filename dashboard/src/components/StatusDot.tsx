const COLOR: Record<string, string> = {
  passed: "var(--status-passed)",
  failed: "var(--status-failed)",
  errored: "var(--status-errored)",
  skipped: "var(--status-skipped)",
};

/** A status colour is never alone: the word (or a label naming it) always follows. */
export default function StatusDot({ status, label }: { status: string; label?: string }) {
  return (
    <span style={{ whiteSpace: "nowrap" }}>
      <span className="status-dot" style={{ background: COLOR[status] ?? "var(--text-muted)" }} />
      {label ?? status}
    </span>
  );
}
