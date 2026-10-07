import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { formatPassRate, getBranches, getTrends } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import NarrowMeta from "../components/NarrowMeta";
import FilterBar from "../components/FilterBar";
import SortableTh from "../components/SortableTh";
import { nextSort, parseSort, sortPatch, sortRows, SortState } from "../lib/sort";
import { oneOf, useUrlState } from "../lib/useUrlState";

const inkLegend = (value: string) => (
  <span className="muted">{value}</span>
);
const tooltipStyles = {
  contentStyle: { background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 6 },
  itemStyle: { color: "var(--text-primary)" },
  labelStyle: { color: "var(--text-secondary)" },
} as const;

function useBranchTrend(projectId: number, days: number, tz: string, branch: string) {
  return useQuery({
    queryKey: ["trends", projectId, days, branch, "", "compare"],
    queryFn: () => getTrends(projectId, { days, tz, branch }),
    enabled: branch !== "",
  });
}

const DEFAULTS = { days: "30", a: "", b: "", sort: "last", dir: "" } as const;
const SORT_KEYS = ["branch", "runs", "rate", "failed", "last"] as const;
type SortKey = (typeof SORT_KEYS)[number];
const DEFAULT_SORT: SortState<SortKey> = { key: "last", dir: "desc" };
const DAYS = ["7", "30", "90"] as const;

export default function BranchesPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const { values, update } = useUrlState(DEFAULTS, 1);
  const days = Number(oneOf(values.days, DAYS, "30"));
  const branchA = values.a;
  const branchB = values.b;
  const sort = parseSort(values.sort, values.dir, SORT_KEYS, DEFAULT_SORT);
  const onSort = (key: SortKey) => {
    const next = nextSort(sort, key, key === "branch" ? "asc" : "desc");
    update(sortPatch(next, DEFAULT_SORT));
  };

  const branchesQuery = useQuery({
    queryKey: ["branches", id, days],
    queryFn: () => getBranches(id, { days }),
  });

  const trendA = useBranchTrend(id, days, tz, branchA);
  const trendB = useBranchTrend(id, days, tz, branchB);

  const rows = sortRows(branchesQuery.data ?? [], sort, (r, key) =>
    key === "branch" ? r.branch : key === "runs" ? r.runs : key === "rate" ? r.pass_rate : key === "failed" ? r.failed : Date.parse(r.last_seen));
  const named = rows.filter((r) => r.branch !== null);

  // One row per date, each series in its own key; nulls leave gaps.
  const compareData = (() => {
    if (!trendA.data || !trendB.data) return [];
    const byDate = new Map<string, { date: string; a: number | null; b: number | null }>();
    for (const d of trendA.data.days) {
      byDate.set(d.date, { date: d.date, a: d.pass_rate === null ? null : d.pass_rate * 100, b: null });
    }
    for (const d of trendB.data.days) {
      const row = byDate.get(d.date) ?? { date: d.date, a: null, b: null };
      row.b = d.pass_rate === null ? null : d.pass_rate * 100;
      byDate.set(d.date, row);
    }
    return [...byDate.values()].sort((x, y) => x.date.localeCompare(y.date));
  })();

  return (
    <section>
      <h2 className="sr-only">Branches</h2>
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
          Compare A
          <select value={branchA} onChange={(e) => update({ a: e.target.value })}>
            <option value="">—</option>
            {named.map((r) => (
              <option key={r.branch} value={r.branch!}>{r.branch}</option>
            ))}
          </select>
        </label>
        <label>
          Compare B
          <select value={branchB} onChange={(e) => update({ b: e.target.value })}>
            <option value="">—</option>
            {named.map((r) => (
              <option key={r.branch} value={r.branch!}>{r.branch}</option>
            ))}
          </select>
        </label>
      </FilterBar>

      {branchesQuery.error != null && (
        <ErrorBanner error={branchesQuery.error} onRetry={() => branchesQuery.refetch()} />
      )}
      {branchesQuery.isPending && <p className="muted">Loading branches…</p>}
      {branchesQuery.data && rows.length === 0 && (
        <p className="muted">No branches with runs in the last {days} days.</p>
      )}

      {branchA && branchB && (
        <div className="card">
          <h3>Pass rate: {branchA} vs {branchB}</h3>
          {(trendA.error != null || trendB.error != null) && (
            <ErrorBanner error={trendA.error ?? trendB.error} />
          )}
          <div
            role="img"
            aria-label={`Daily pass rate of ${branchA} and ${branchB} over the last ${days} days; the table below carries the per-branch numbers.`}
          >
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={compareData}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="date" stroke="var(--text-muted)" tickLine={false} />
              <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} stroke="var(--text-muted)" tickLine={false} />
              <Tooltip
                {...tooltipStyles}
                cursor={{ stroke: "var(--grid)" }}
                formatter={(v) => `${Number(v).toFixed(1)}%`}
              />
              <Legend formatter={inkLegend} />
              <Line dataKey="a" name={branchA} stroke="var(--series-1)" strokeWidth={2} dot={false} connectNulls={false} />
              <Line dataKey="b" name={branchB} stroke="var(--series-2)" strokeWidth={2} dot={false} connectNulls={false} />
            </LineChart>
          </ResponsiveContainer>
          </div>
        </div>
      )}

      {rows.length > 0 && (
        <div className="card" tabIndex={0} role="region" aria-label="Branches">
          <table className="data">
            <thead>
              <tr>
                <SortableTh label="Branch" sortKey="branch" sort={sort} onSort={onSort} />
                <SortableTh label="Runs" sortKey="runs" sort={sort} onSort={onSort} />
                <SortableTh label="Pass rate" sortKey="rate" sort={sort} onSort={onSort} />
                <th className="hide-narrow">Passed</th>
                <SortableTh label="Failed" sortKey="failed" sort={sort} onSort={onSort} />
                <th className="hide-narrow">Errored</th><th className="hide-narrow">Skipped</th>
                <SortableTh label="Last run" sortKey="last" sort={sort} onSort={onSort} className="hide-narrow" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.branch ?? "(none)"}>
                  <td>
                    {r.branch ?? <span className="muted">no branch</span>}
                    <NarrowMeta items={[
                      { label: "Passed", value: r.passed },
                      { label: "Errored", value: r.errored },
                      { label: "Skipped", value: r.skipped },
                      { label: "Last run", value: new Date(r.last_seen).toLocaleString() },
                    ]} />
                  </td>
                  <td>{r.runs}</td>
                  <td>{formatPassRate(r.pass_rate)}</td>
                  <td className="hide-narrow">{r.passed}</td>
                  <td>{r.failed}</td>
                  <td className="hide-narrow">{r.errored}</td>
                  <td className="hide-narrow">{r.skipped}</td>
                  <td className="hide-narrow">{new Date(r.last_seen).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
