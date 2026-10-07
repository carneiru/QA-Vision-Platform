import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { formatDuration, formatPassRate, getHistory } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import StatusDot from "../components/StatusDot";
import Message from "../components/Message";
import { oneOf, useUrlState } from "../lib/useUrlState";

const DEFAULTS = { days: "30", branch: "" } as const;
const DAYS = ["7", "30", "90"] as const;

export default function HistoryPage() {
  const { projectId, testKey } = useParams();
  const id = Number(projectId);
  const { values, update } = useUrlState(DEFAULTS, 1);
  const days = Number(oneOf(values.days, DAYS, "30"));
  const branch = values.branch;

  const query = useQuery({
    queryKey: ["history", id, testKey, days, branch],
    queryFn: () => getHistory(id, testKey!, { days, branch: branch || undefined, limit: 100 }),
  });

  const data = query.data;

  return (
    <section>
      <p>
        <Link className="link-arrow" to=".." relative="path"><ArrowLeft size={14} aria-hidden="true" /> All tests</Link>
      </p>
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
          Branch
          {/* replace: every keystroke queries, so Back must not step through each letter */}
          <input value={branch} onChange={(e) => update({ branch: e.target.value }, { replace: true })} placeholder="all" />
        </label>
      </FilterBar>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading history…</p>}

      {data && (
        <>
          <h2>{data.name}</h2>
          <p className="muted">{data.suite} / {data.class_name}</p>
          <div className="tiles">
            <div className="card">
              <div className="tile-value">{data.summary.runs}</div>
              <div className="tile-label">Executions ({days} days)</div>
            </div>
            <div className="card">
              <div className="tile-value">{formatPassRate(data.summary.pass_rate)}</div>
              <div className="tile-label">Pass rate</div>
            </div>
            <div className="card">
              <div className="tile-value">{formatDuration(data.summary.avg_duration_ms)}</div>
              <div className="tile-label">Avg duration</div>
            </div>
          </div>
          {data.executions.length === 0 ? (
            <p className="muted">No executions in the last {days} days.</p>
          ) : (
            <div className="card" tabIndex={0} role="region" aria-label="Executions">
              <table className="data">
                <thead>
                  <tr>
                    <th>Run</th><th>Started</th><th>Branch</th><th className="hide-narrow">Commit</th>
                    <th className="hide-narrow">Environment</th><th>Status</th><th className="hide-narrow">Duration</th><th className="hide-narrow">Message</th>
                  </tr>
                </thead>
                <tbody>
                  {data.executions.map((x) => (
                    <tr key={`${x.run_id}-${x.started_at}`}>
                      <td><Link to={`/projects/${projectId}/runs/${x.run_id}`}>#{x.run_id}</Link></td>
                      <td>{new Date(x.started_at).toLocaleString()}</td>
                      <td>{x.branch ?? "—"}</td>
                      <td className="hide-narrow">{x.commit_sha ? x.commit_sha.slice(0, 7) : "—"}</td>
                      <td className="hide-narrow">{x.environment ?? "—"}</td>
                      <td><StatusDot status={x.status} /></td>
                      <td className="hide-narrow">{formatDuration(x.duration_ms)}</td>
                      <td className="hide-narrow"><Message text={x.message} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
