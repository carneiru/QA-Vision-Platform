import { ReactNode, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Download, Printer } from "lucide-react";
import {
  StatsRow,
  formatDuration,
  formatPassRate,
  getBranches,
  getFlaky,
  getTests,
  getTrends,
} from "../api/analytics";
import { getProject } from "../api/orgs";
import { downloadCsv, toCsv } from "../lib/csv";
import { fetchAllTests } from "../lib/exportData";
import ErrorBanner from "../components/ErrorBanner";

const PERIODS = [7, 30, 90];
const TOP = 10;
// The Flaky page's defaults, so the report and that page agree
const FLAKY_MIN_RUNS = 5;
const FLAKY_MIN_FLIP_RATE = 0.3;

const number = new Intl.NumberFormat();

function testLabel(r: { suite: string; class_name: string; name: string }): string {
  return [r.suite, r.class_name, r.name].filter(Boolean).join(" › ");
}

function Section({ title, children, loading, empty }: { title: string; children: ReactNode; loading: boolean; empty: boolean }) {
  return (
    <section className="card report-section">
      <h3>{title}</h3>
      {loading ? <p className="muted">Loading…</p> : empty ? <p className="muted">Nothing in this period.</p> : children}
    </section>
  );
}

function TestTable({ caption, rows, value }: { caption: string; rows: StatsRow[]; value: (r: StatsRow) => ReactNode }) {
  return (
    <table className="data">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr><th>Test</th><th>Runs</th><th>Pass rate</th><th>{caption.startsWith("Slowest") ? "Average duration" : "Failures"}</th></tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.test_key}>
            <td className="wrap-anywhere">{testLabel(r)}</td>
            <td>{number.format(r.runs)}</td>
            <td>{formatPassRate(r.pass_rate)}</td>
            <td>{value(r)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ReportPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [days, setDays] = useState(30);
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvError, setCsvError] = useState<unknown>(null);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

  const project = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id) });
  const trends = useQuery({
    queryKey: ["report-trends", id, days, tz],
    queryFn: () => getTrends(id, { days, tz, bucket: "week" }),
  });
  const failing = useQuery({
    queryKey: ["report-failing", id, days],
    queryFn: () => getTests(id, { days, sort: "failures", limit: TOP, offset: 0 }),
  });
  const slowest = useQuery({
    queryKey: ["report-slowest", id, days],
    queryFn: () => getTests(id, { days, sort: "duration", limit: TOP, offset: 0 }),
  });
  const flaky = useQuery({
    queryKey: ["report-flaky", id, days],
    queryFn: () => getFlaky(id, { windowDays: days, minRuns: FLAKY_MIN_RUNS, minFlipRate: FLAKY_MIN_FLIP_RATE }),
  });
  const branches = useQuery({ queryKey: ["report-branches", id, days], queryFn: () => getBranches(id, { days, limit: TOP }) });

  const weeks = trends.data?.days ?? [];
  const totals = weeks.reduce(
    (t, w) => ({
      runs: t.runs + w.runs, total: t.total + w.total, passed: t.passed + w.passed,
      broken: t.broken + w.failed + w.errored, skipped: t.skipped + w.skipped,
    }),
    { runs: 0, total: 0, passed: 0, broken: 0, skipped: 0 },
  );
  const considered = totals.total - totals.skipped;
  const passRate = considered > 0 ? totals.passed / considered : null;
  const failingRows = (failing.data ?? []).filter((r) => r.failed + r.errored > 0);
  const errors = [trends, failing, slowest, flaky, branches].map((q) => q.error).filter((e) => e != null);

  async function onCsv() {
    setCsvBusy(true);
    setCsvError(null);
    try {
      const all = await fetchAllTests(id, { days, sort: "failures" });
      downloadCsv(
        `report-project-${id}-${days}d.csv`,
        toCsv(
          ["suite", "class_name", "name", "runs", "passed", "failed", "errored", "skipped", "pass_rate",
           "avg_duration_ms", "last_status", "last_seen"],
          all.map((r) => [r.suite, r.class_name, r.name, r.runs, r.passed, r.failed, r.errored, r.skipped,
            r.pass_rate, r.avg_duration_ms, r.last_status, r.last_seen]),
        ),
      );
    } catch (err) {
      setCsvError(err);
    } finally {
      setCsvBusy(false);
    }
  }

  const title = `${project.data?.name ?? "Project"}: quality report`;

  return (
    <div className="report">
      <div className="report-head">
        <div>
          <h2>{title}</h2>
          <p className="muted">
            Last {days} days, generated {new Date().toLocaleString()} ({tz}).
          </p>
        </div>
        <div className="report-actions no-print">
          <label>
            Period
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {PERIODS.map((d) => <option key={d} value={d}>Last {d} days</option>)}
            </select>
          </label>
          <button onClick={() => window.print()}>
            <Printer size={15} aria-hidden="true" /> Save as PDF
          </button>
          <button onClick={onCsv} disabled={csvBusy}>
            <Download size={15} aria-hidden="true" /> {csvBusy ? "Preparing…" : "Download CSV"}
          </button>
        </div>
      </div>
      {errors.length > 0 && <ErrorBanner error={errors[0]} />}
      {csvError != null && <ErrorBanner error={csvError} />}

      <section className="card report-section" aria-label="Summary">
        <h3>Summary</h3>
        {trends.isPending ? (
          <p className="muted">Loading…</p>
        ) : (
          <dl className="report-figures">
            <div><dt>Runs</dt><dd>{number.format(totals.runs)}</dd></div>
            <div><dt>Test executions</dt><dd>{number.format(totals.total)}</dd></div>
            <div><dt>Pass rate</dt><dd>{formatPassRate(passRate)}</dd></div>
            <div><dt>Failures</dt><dd>{number.format(totals.broken)}</dd></div>
          </dl>
        )}
        <p className="muted report-note">Pass rate leaves skipped tests out: passed ÷ (executions − skipped).</p>
      </section>

      <Section title="Pass rate by week" loading={trends.isPending} empty={weeks.length === 0}>
        <table className="data">
          <caption className="sr-only">Pass rate by week</caption>
          <thead>
            <tr><th>Week of</th><th>Runs</th><th>Executions</th><th>Failures</th><th>Pass rate</th><th>Average run</th></tr>
          </thead>
          <tbody>
            {weeks.map((w) => (
              <tr key={w.date}>
                <td>{new Date(`${w.date}T00:00:00`).toLocaleDateString()}</td>
                <td>{number.format(w.runs)}</td>
                <td>{number.format(w.total)}</td>
                <td>{number.format(w.failed + w.errored)}</td>
                <td>{formatPassRate(w.pass_rate)}</td>
                <td>{formatDuration(w.avg_run_duration_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title={`Most failing tests (top ${TOP})`} loading={failing.isPending} empty={failingRows.length === 0}>
        <TestTable caption="Most failing tests" rows={failingRows} value={(r) => number.format(r.failed + r.errored)} />
      </Section>

      <Section title={`Slowest tests (top ${TOP})`} loading={slowest.isPending} empty={(slowest.data ?? []).length === 0}>
        <TestTable caption="Slowest tests" rows={slowest.data ?? []} value={(r) => formatDuration(r.avg_duration_ms)} />
      </Section>

      <Section title="Flaky tests" loading={flaky.isPending} empty={(flaky.data ?? []).length === 0}>
        <table className="data">
          <caption className="sr-only">Flaky tests</caption>
          <thead><tr><th>Test</th><th>Runs</th><th>Why flaky</th></tr></thead>
          <tbody>
            {(flaky.data ?? []).slice(0, TOP).map((f) => (
              <tr key={f.test_key}>
                <td className="wrap-anywhere">{testLabel(f)}</td>
                <td>{number.format(f.runs)}</td>
                <td>
                  {f.reason === "same_commit"
                    ? `Passed and failed on the same commit (${f.commits.length})`
                    : `Flipped ${f.flips ?? 0} times (${formatPassRate(f.flip_rate)} of runs)`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title={`Branches (top ${TOP})`} loading={branches.isPending} empty={(branches.data ?? []).length === 0}>
        <table className="data">
          <caption className="sr-only">Branches</caption>
          <thead><tr><th>Branch</th><th>Runs</th><th>Failures</th><th>Pass rate</th></tr></thead>
          <tbody>
            {(branches.data ?? []).map((b) => (
              <tr key={b.branch ?? "(none)"}>
                <td>{b.branch ?? <span className="muted">no branch</span>}</td>
                <td>{number.format(b.runs)}</td>
                <td>{number.format(b.failed + b.errored)}</td>
                <td>{formatPassRate(b.pass_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}
