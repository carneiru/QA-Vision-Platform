const COLOR: Record<string, string> = {
  passed: "var(--status-passed)",
  failed: "var(--status-failed)",
  errored: "var(--status-errored)",
  skipped: "var(--status-skipped)",
};

const SHAPE = new Set(["passed", "failed", "errored", "skipped"]);

/** A status colour is never alone: the word (or a label naming it) always follows, and the dot's shape differs too (circle, triangle, square, ring). */
export default function StatusDot({ status, label }: { status: string; label?: string }) {
  return (
    <span style={{ whiteSpace: "nowrap" }}>
      <span className={`status-dot shape-${SHAPE.has(status) ? status : "other"}`} style={{ background: COLOR[status] ?? "var(--text-muted)" }} aria-hidden="true" />
      {label ?? status}
    </span>
  );
}
