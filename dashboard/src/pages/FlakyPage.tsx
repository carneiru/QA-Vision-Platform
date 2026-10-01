import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { formatPassRate, getFlaky } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import StatusDot from "../components/StatusDot";

export default function FlakyPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [windowDays, setWindowDays] = useState(14);
  const [minRuns, setMinRuns] = useState(5);
  const [minFlipRate, setMinFlipRate] = useState(0.3);
  const [branch, setBranch] = useState("");

  const query = useQuery({
    queryKey: ["flaky", id, windowDays, minRuns, minFlipRate, branch],
    queryFn: () => getFlaky(id, { windowDays, minRuns, minFlipRate, branch: branch || undefined }),
  });

  const rows = query.data ?? [];

  return (
    <section>
      <h2 className="sr-only">Flaky tests</h2>
      <FilterBar>
        <label>
          Window (days)
          <select value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))}>
            <option value={7}>7</option>
            <option value={14}>14</option>
            <option value={30}>30</option>
          </select>
        </label>
        <label>
          Min runs
          <input
            type="number" min={2} max={1000} value={minRuns}
            onChange={(e) => setMinRuns(Number(e.target.value))}
          />
        </label>
        <label>
          Min flip rate
          <input
            type="number" min={0} max={1} step={0.05} value={minFlipRate}
            onChange={(e) => setMinFlipRate(Number(e.target.value))}
          />
        </label>
        <label>
          Branch
          <input value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="all" />
        </label>
      </FilterBar>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading flaky tests…</p>}
      {query.data && rows.length === 0 && (
        <p className="muted">No flaky tests in the last {windowDays} days.</p>
      )}

      {rows.length > 0 && (
        <div className="card">
          <table className="data">
            <thead>
              <tr>
                <th>Test</th><th>Reason</th><th>Flips</th><th>Flip rate</th>
                <th>Runs</th><th>Last status</th><th>Commits</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.test_key}>
                  <td>
                    <Link to={`../tests/${encodeURIComponent(r.test_key)}`} relative="path">
                      {r.name}
                    </Link>
                    <div className="muted">{r.suite} / {r.class_name}</div>
                  </td>
                  <td>{r.reason === "same_commit" ? "Confirmed" : "Suspected"}</td>
                  <td>{r.flips ?? "—"}</td>
                  <td>{formatPassRate(r.flip_rate)}</td>
                  <td>{r.runs}</td>
                  <td><StatusDot status={r.last_status} /></td>
                  <td>
                    {r.commits.length === 0 ? (
                      <span className="muted">—</span>
                    ) : (
                      <details>
                        <summary>{r.commits.length} commit(s)</summary>
                        <ul>
                          {r.commits.map((c, i) => (
                            <li key={i}>
                              {c.commit_sha.slice(0, 7)}
                              {c.environment && <span className="muted"> · {c.environment}</span>}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
