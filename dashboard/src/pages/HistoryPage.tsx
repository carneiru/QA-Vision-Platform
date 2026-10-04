import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { formatDuration, formatPassRate, getHistory } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import StatusDot from "../components/StatusDot";
import Message from "../components/Message";

export default function HistoryPage() {
  const { projectId, testKey } = useParams();
  const id = Number(projectId);
  const [days, setDays] = useState(30);
  const [branch, setBranch] = useState("");

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
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>7</option>
            <option value={30}>30</option>
            <option value={90}>90</option>
          </select>
        </label>
        <label>
          Branch
          <input value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="all" />
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
            <div className="card">
              <table className="data">
                <thead>
                  <tr>
                    <th>Run</th><th>Started</th><th>Branch</th><th>Commit</th>
                    <th>Environment</th><th>Status</th><th>Duration</th><th>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {data.executions.map((x) => (
                    <tr key={`${x.run_id}-${x.started_at}`}>
                      <td>{x.run_id}</td>
                      <td>{new Date(x.started_at).toLocaleString()}</td>
                      <td>{x.branch ?? "—"}</td>
                      <td>{x.commit_sha ? x.commit_sha.slice(0, 7) : "—"}</td>
                      <td>{x.environment ?? "—"}</td>
                      <td><StatusDot status={x.status} /></td>
                      <td>{formatDuration(x.duration_ms)}</td>
                      <td><Message text={x.message} /></td>
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
