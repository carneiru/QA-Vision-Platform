const COLOR: Record<string, string> = {
  passed: "var(--status-passed)",
  failed: "var(--status-failed)",
  errored: "var(--status-errored)",
  skipped: "var(--status-skipped)",
};

export default function StatusDot({ status }: { status: string }) {
  return (
    <span>
      <span className="status-dot" style={{ background: COLOR[status] ?? "var(--text-muted)" }} />
      {status}
    </span>
  );
}
