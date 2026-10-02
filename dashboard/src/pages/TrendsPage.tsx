import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { TrendBucket, formatDuration, formatPassRate, getTrends } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";

// Legend/tooltip text stays in ink tokens; the colored swatch carries identity.
const inkLegend = (value: string) => (
  <span style={{ color: "var(--text-secondary)" }}>{value}</span>
);
const tooltipStyles = {
  contentStyle: { background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 6 },
  itemStyle: { color: "var(--text-primary)" },
  labelStyle: { color: "var(--text-secondary)" },
} as const;

const STATUS = [
  { key: "passed", label: "Passed", color: "var(--status-passed)" },
  { key: "failed", label: "Failed", color: "var(--status-failed)" },
  { key: "errored", label: "Errored", color: "var(--status-errored)" },
  { key: "skipped", label: "Skipped", color: "var(--status-skipped)" },
] as const;

export default function TrendsPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const [days, setDays] = useState(30);
  const [bucket, setBucket] = useState<TrendBucket>("day");
  // Text filters are drafts until Apply: per-keystroke refetching is chatty
  // against the shared gateway rate limit.
  const [branchInput, setBranchInput] = useState("");
  const [environmentInput, setEnvironmentInput] = useState("");
  const [branch, setBranch] = useState("");
  const [environment, setEnvironment] = useState("");
  const [showTable, setShowTable] = useState(false);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setBranch(branchInput.trim());
    setEnvironment(environmentInput.trim());
  }

  const query = useQuery({
    queryKey: ["trends", id, days, bucket, branch, environment],
    queryFn: () =>
      getTrends(id, { days, tz, bucket, branch: branch || undefined, environment: environment || undefined }),
  });

  const trendDays = query.data?.days ?? [];
  const totals = trendDays.reduce(
    (acc, d) => ({
      runs: acc.runs + d.runs,
      passed: acc.passed + d.passed,
      counted: acc.counted + d.passed + d.failed + d.errored,
    }),
    { runs: 0, passed: 0, counted: 0 },
  );
  const windowRate = totals.counted > 0 ? totals.passed / totals.counted : null;
  const rateData = trendDays.map((d) => ({
    date: d.date,
    ratePct: d.pass_rate === null ? null : d.pass_rate * 100,
  }));

  return (
    <section>
      <h2 className="sr-only">Trends</h2>
      <form onSubmit={applyFilters}>
        <FilterBar>
          <label>
            Days
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={7}>7</option>
              <option value={30}>30</option>
              <option value={90}>90</option>
            </select>
          </label>
          <label>
            View
            <select value={bucket} onChange={(e) => setBucket(e.target.value as TrendBucket)}>
              <option value="day">Daily</option>
              <option value="week">Weekly</option>
              <option value="month">Monthly</option>
            </select>
          </label>
          <label>
            Branch
            <input value={branchInput} onChange={(e) => setBranchInput(e.target.value)} placeholder="all" />
          </label>
          <label>
            Environment
            <input
              value={environmentInput}
              onChange={(e) => setEnvironmentInput(e.target.value)}
              placeholder="all"
            />
          </label>
          <button type="submit">Apply</button>
          <button type="button" onClick={() => setShowTable((v) => !v)}>
            {showTable ? "Hide data" : "View data"}
          </button>
        </FilterBar>
      </form>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading trends…</p>}
      {query.data && trendDays.length === 0 && (
        <p className="muted">
          No runs in the last {days} days{branch && ` on ${branch}`}{environment && ` in ${environment}`}.
        </p>
      )}

      {trendDays.length > 0 && (
        <>
          <div className="tiles">
            <div className="card">
              <div className="tile-value">{totals.runs}</div>
              <div className="tile-label">Runs ({days} days)</div>
            </div>
            <div className="card">
              <div className="tile-value">{formatPassRate(windowRate)}</div>
              <div className="tile-label">Pass rate ({days} days)</div>
            </div>
            <div className="card">
              <div className="tile-value">
                {formatDuration(trendDays[trendDays.length - 1].avg_run_duration_ms)}
              </div>
              <div className="tile-label">Avg run duration (last day)</div>
            </div>
          </div>

          <div className="card">
            <h3>Results per day</h3>
            <div
              role="img"
              aria-label={`Stacked bars of passed, failed, errored and skipped results per day over the last ${days} days. The View data button shows the same numbers as a table.`}
            >
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={trendDays} barCategoryGap="20%">
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="date" stroke="var(--text-muted)" tickLine={false} />
                <YAxis allowDecimals={false} stroke="var(--text-muted)" tickLine={false} />
                <Tooltip {...tooltipStyles} cursor={{ fill: "var(--grid)", fillOpacity: 0.5 }} />
                <Legend formatter={inkLegend} />
                {STATUS.map((s, i) => (
                  <Bar
                    key={s.key}
                    dataKey={s.key}
                    name={s.label}
                    stackId="status"
                    fill={s.color}
                    stroke="var(--surface-1)"
                    strokeWidth={1}
                    radius={i === STATUS.length - 1 ? [4, 4, 0, 0] : undefined}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
            </div>
          </div>

          <div className="card" style={{ marginTop: 12 }}>
            <h3>Pass rate</h3>
            <div
              role="img"
              aria-label={`Daily pass rate line over the last ${days} days. The View data button shows the same numbers as a table.`}
            >
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={rateData}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="date" stroke="var(--text-muted)" tickLine={false} />
                <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} stroke="var(--text-muted)" tickLine={false} />
                <Tooltip
                  {...tooltipStyles}
                  cursor={{ stroke: "var(--grid)" }}
                  formatter={(v) => [`${Number(v).toFixed(1)}%`, "Pass rate"]}
                />
                <Line dataKey="ratePct" stroke="var(--accent)" strokeWidth={2} dot={false} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
            </div>
          </div>
        </>
      )}

      {showTable && query.data && (
        <div className="card" style={{ marginTop: 12 }}>
          <table className="data">
            <thead>
              <tr>
                <th>Date</th><th>Runs</th><th>Passed</th><th>Failed</th>
                <th>Errored</th><th>Skipped</th><th>Pass rate</th><th>Avg duration</th>
              </tr>
            </thead>
            <tbody>
              {trendDays.map((d) => (
                <tr key={d.date}>
                  <td>{d.date}</td><td>{d.runs}</td><td>{d.passed}</td><td>{d.failed}</td>
                  <td>{d.errored}</td><td>{d.skipped}</td>
                  <td>{formatPassRate(d.pass_rate)}</td>
                  <td>{formatDuration(d.avg_run_duration_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
