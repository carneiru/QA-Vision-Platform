import { useQuery } from "@tanstack/react-query";
import { formatPassRate, getFlaky } from "../../../api/analytics";
import { testLabel } from "../../../api/report";
import ErrorBanner from "../../../components/ErrorBanner";
import { SkeletonStatus } from "../../../components/Skeleton";
import { type ReportFilters, spanDays } from "../useReportFilters";
import { type Gate, REPORT_STALE_MS } from "../useReportRequest";

const number = new Intl.NumberFormat();
// The Flaky page's defaults, so the report and that page agree
const FLAKY_MIN_RUNS = 5;
const FLAKY_MIN_FLIP_RATE = 0.3;
const TOP = 10;

/** Phase 1 keeps the Flaky table (spec: Section 1, "Flaky tests in P1"). /flaky only knows "the last N days" and a
 *  branch, so a custom range is read up to today (plan Ruling 6), and area or suite keys filter its rows here. */
export default function FlakySection({ projectId, gate, filters, branch, today }: {
  projectId: number;
  gate: Gate;
  filters: ReportFilters;
  branch: string | null;
  today: string;
}) {
  const windowDays = Math.min(90, spanDays(filters.from, today));
  const flaky = useQuery({
    queryKey: ["report-flaky", projectId, windowDays, branch],
    queryFn: () => getFlaky(projectId, { windowDays, minRuns: FLAKY_MIN_RUNS, minFlipRate: FLAKY_MIN_FLIP_RATE, branch: branch ?? undefined }),
    enabled: gate.state === "ready",
    staleTime: REPORT_STALE_MS,
    retry: false,
  });
  const keys = gate.state === "ready" && gate.base.test_keys ? new Set(gate.base.test_keys) : null;
  const rows = (flaky.data ?? []).filter((r) => !keys || keys.has(r.test_key.toLowerCase())).slice(0, TOP);

  let body;
  if (gate.state === "blocked") body = <p className="muted">{gate.message}</p>;
  else if (flaky.error != null) body = <ErrorBanner error={flaky.error} onRetry={() => void flaky.refetch()} />;
  else if (gate.state === "wait" || flaky.isPending) {
    body = <SkeletonStatus label="Loading flaky tests…"><span className="skeleton skeleton-block" style={{ height: 160 }} aria-hidden="true" /></SkeletonStatus>;
  } else if (rows.length === 0) body = <p className="muted">No flaky tests in this period.</p>;
  else {
    body = (
      <table className="data">
        <caption className="sr-only">Flaky tests</caption>
        <thead><tr><th scope="col">Test</th><th scope="col" className="num">Runs</th><th scope="col">Why flaky</th></tr></thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f.test_key}>
              <td className="wrap-anywhere">{testLabel(f)}</td>
              <td className="num">{number.format(f.runs)}</td>
              <td>{f.reason === "same_commit"
                ? `Passed and failed on the same commit (${f.commits.length})`
                : `Flipped ${f.flips ?? 0} times (${formatPassRate(f.flip_rate)} of runs)`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  return (
    <section className="card report-section" aria-labelledby="report-flaky">
      <div className="report-section-head"><h2 id="report-flaky">Flaky tests</h2></div>
      <p className="muted report-note">
        Covers the last {windowDays} days. Environment, CI provider and origin filters do not apply here.
      </p>
      {body}
    </section>
  );
}
