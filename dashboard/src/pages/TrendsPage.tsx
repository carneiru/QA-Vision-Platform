import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { oneOf, useDraft, useUrlState } from "../lib/useUrlState";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { TrendBucket, formatDuration, formatPassRate, getTrends } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import { SkeletonCard, SkeletonStatus } from "../components/Skeleton";
import FilterBar from "../components/FilterBar";
import { ChartPatternDefs, DataTableDisclosure, LegendSeries, PATTERN, SeriesLegend } from "../components/ChartKit";
import { formatPointLabel, formatTick } from "../lib/chartFormat";
import { useMediaQuery } from "../lib/useMediaQuery";
import PageHeader from "../components/PageHeader";

const tooltipStyles = {
  contentStyle: { background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 6 },
  itemStyle: { color: "var(--text-primary)" },
  labelStyle: { color: "var(--text-secondary)" },
} as const;

// Colour plus texture (solid, stripes, dots, lines): the bars stay readable without telling hues apart.
const STATUS = [
  { key: "passed", label: "Passed", paint: "var(--status-passed)" },
  { key: "failed", label: "Failed", paint: `url(#${PATTERN.failed})` },
  { key: "errored", label: "Errored", paint: `url(#${PATTERN.errored})` },
  { key: "skipped", label: "Skipped", paint: `url(#${PATTERN.skipped})` },
] as const;
const LEGEND: LegendSeries[] = STATUS.map((s) => ({ key: s.key, label: s.label, paint: s.paint }));
const axisTick = { fill: "var(--text-secondary)", fontSize: 12 } as const;
const NOUN = { day: "day", week: "week", month: "month" } as const;

const DEFAULTS = { days: "30", bucket: "day", branch: "", environment: "" } as const;
const DAYS = ["7", "30", "90"] as const;
const BUCKETS = ["day", "week", "month"] as const;

export default function TrendsPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const { values, update } = useUrlState(DEFAULTS, 1);
  const days = Number(oneOf(values.days, DAYS, "30"));
  const bucket = oneOf(values.bucket, BUCKETS, "day") as TrendBucket;
  const { branch, environment } = values;
  // Text filters are drafts until Apply: per-keystroke refetching is chatty
  // against the shared gateway rate limit.
  const [branchInput, setBranchInput, commitBranch] = useDraft(branch);
  const [environmentInput, setEnvironmentInput, commitEnvironment] = useDraft(environment);
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
  const narrow = useMediaQuery("(max-width: 640px)");
  const toggleSeries = (key: string) =>
    setHidden((h) => {
      const next = new Set(h);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    update({ branch: commitBranch((raw) => raw.trim()), environment: commitEnvironment((raw) => raw.trim()) });
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
  const unit = NOUN[bucket];
  const tick = (v: string) => formatTick(v, bucket);
  const label = (v: unknown) => formatPointLabel(String(v), bucket);
  const sums = trendDays.reduce(
    (a, d) => ({ passed: a.passed + d.passed, failed: a.failed + d.failed, errored: a.errored + d.errored, skipped: a.skipped + d.skipped }),
    { passed: 0, failed: 0, errored: 0, skipped: 0 },
  );
  const worst = trendDays.reduce<(typeof trendDays)[number] | null>((w, d) => (d.failed + d.errored > (w ? w.failed + w.errored : 0) ? d : w), null);
  const resultsSummary =
    `Stacked bars of results per ${unit}, ${formatPointLabel(trendDays[0]?.date ?? "", bucket)} to ${formatPointLabel(trendDays[trendDays.length - 1]?.date ?? "", bucket)}: ` +
    `${sums.passed} passed, ${sums.failed} failed, ${sums.errored} errored, ${sums.skipped} skipped.` +
    (worst ? ` Most failing or errored: ${formatPointLabel(worst.date, bucket)}, ${worst.failed + worst.errored}.` : " No failures.");
  const rated = trendDays.filter((d) => d.pass_rate !== null);
  const lowest = rated.reduce<(typeof trendDays)[number] | null>((w, d) => (!w || (d.pass_rate as number) < (w.pass_rate as number) ? d : w), null);
  const rateSummary = rated.length === 0
    ? `Pass rate per ${unit}: no ${unit} had counted results.`
    : `Pass rate per ${unit}, from ${formatPassRate(rated[0].pass_rate)} to ${formatPassRate(rated[rated.length - 1].pass_rate)}; lowest ${formatPassRate(lowest?.pass_rate ?? null)} on ${formatPointLabel(lowest?.date ?? "", bucket)}.`;
  const rateData = trendDays.map((d) => ({
    date: d.date,
    ratePct: d.pass_rate === null ? null : d.pass_rate * 100,
  }));

  return (
    <section>
      <PageHeader title="Trends" />
      <ChartPatternDefs />
      <form onSubmit={applyFilters}>
        <FilterBar>
          <label>
            Days
            <select value={String(days)} onChange={(e) => update({ days: e.target.value })}>
              <option value={7}>7</option>
              <option value={30}>30</option>
              <option value={90}>90</option>
            </select>
          </label>
          <label>
            View
            <select value={bucket} onChange={(e) => update({ bucket: e.target.value })}>
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
        </FilterBar>
      </form>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && (
        <SkeletonStatus label="Loading trends…">
          <div className="tiles">
            <SkeletonCard height={34} />
            <SkeletonCard height={34} />
            <SkeletonCard height={34} />
          </div>
          <SkeletonCard height={280} className="skeleton-chart" />
          <SkeletonCard height={180} className="skeleton-chart" />
        </SkeletonStatus>
      )}
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
              <div className="tile-label">Avg run duration (last {unit})</div>
            </div>
          </div>

          <div className="card">
            <h2 id="trend-results">Results per {unit}</h2>
            <SeriesLegend series={LEGEND} hidden={hidden} onToggle={toggleSeries} label="Show or hide a result type" />
            <figure className="chart-figure" aria-labelledby="trend-results">
              <figcaption className="sr-only">{resultsSummary}</figcaption>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={trendDays} barCategoryGap="20%" accessibilityLayer>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="date" stroke="var(--text-muted)" tick={axisTick} tickLine={false} tickFormatter={tick} minTickGap={narrow ? 36 : 16} interval="preserveStartEnd" />
                  <YAxis allowDecimals={false} stroke="var(--text-muted)" tick={axisTick} tickLine={false} width={narrow ? 32 : 48} />
                  <Tooltip {...tooltipStyles} labelFormatter={label} cursor={{ fill: "var(--grid)", fillOpacity: 0.5 }} />
                  {STATUS.map((s, i) => (
                    <Bar
                      key={s.key}
                      dataKey={s.key}
                      name={s.label}
                      stackId="status"
                      fill={s.paint}
                      hide={hidden.has(s.key)}
                      stroke="var(--surface-1)"
                      strokeWidth={1}
                      radius={i === STATUS.length - 1 ? [4, 4, 0, 0] : undefined}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </figure>
            <DataTableDisclosure name={`results per ${unit}`}>
              <table className="data">
                <thead>
                  <tr><th>{unit === "day" ? "Date" : unit === "week" ? "Week of" : "Month"}</th><th>Runs</th><th>Passed</th><th>Failed</th><th>Errored</th><th>Skipped</th></tr>
                </thead>
                <tbody>
                  {trendDays.map((d) => (
                    <tr key={d.date}>
                      <td>{d.date}</td><td>{d.runs}</td><td>{d.passed}</td><td>{d.failed}</td><td>{d.errored}</td><td>{d.skipped}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DataTableDisclosure>
          </div>

          <div className="card">
            <h2 id="trend-rate">Pass rate per {unit}</h2>
            <figure className="chart-figure" aria-labelledby="trend-rate">
              <figcaption className="sr-only">{rateSummary}</figcaption>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={rateData} accessibilityLayer>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="date" stroke="var(--text-muted)" tick={axisTick} tickLine={false} tickFormatter={tick} minTickGap={narrow ? 36 : 16} interval="preserveStartEnd" />
                  <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} stroke="var(--text-muted)" tick={axisTick} tickLine={false} width={narrow ? 40 : 48} />
                  <Tooltip
                    {...tooltipStyles}
                    labelFormatter={label}
                    cursor={{ stroke: "var(--grid)" }}
                    formatter={(v) => [`${Number(v).toFixed(1)}%`, "Pass rate"]}
                  />
                  <Line dataKey="ratePct" stroke="var(--accent)" strokeWidth={2} dot={{ r: 2.5, fill: "var(--accent)", stroke: "var(--surface-1)" }} connectNulls={false} />
                </LineChart>
              </ResponsiveContainer>
            </figure>
            <DataTableDisclosure name={`pass rate per ${unit}`}>
              <table className="data">
                <thead>
                  <tr><th>{unit === "day" ? "Date" : unit === "week" ? "Week of" : "Month"}</th><th>Pass rate</th><th>Avg duration</th></tr>
                </thead>
                <tbody>
                  {trendDays.map((d) => (
                    <tr key={d.date}>
                      <td>{d.date}</td><td>{formatPassRate(d.pass_rate)}</td><td>{formatDuration(d.avg_run_duration_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DataTableDisclosure>
          </div>
        </>
      )}

    </section>
  );
}
