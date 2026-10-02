import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { RunStatusFilter, getRun } from "../api/runs";
import { formatDuration } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import Message from "../components/Message";
import StatusDot from "../components/StatusDot";

export default function RunDetailPage() {
  const { projectId, runId } = useParams();
  const id = Number(runId);
  const [status, setStatus] = useState<RunStatusFilter | "">("");

  const query = useQuery({
    queryKey: ["run", id, status],
    queryFn: () => getRun(id, status || undefined),
  });

  const run = query.data;

  return (
    <section>
      <p>
        <Link to=".." relative="path">← All runs</Link>
      </p>
      <FilterBar>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value as RunStatusFilter | "")}>
            <option value="">all</option>
            <option value="passed">passed</option>
            <option value="failed">failed</option>
            <option value="errored">errored</option>
            <option value="skipped">skipped</option>
          </select>
        </label>
      </FilterBar>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading run…</p>}

      {run && (
        <>
          <h2>Run #{run.id}</h2>
          <p className="muted">
            <span>{new Date(run.started_at).toLocaleString()}</span> ·{" "}
            <span>{run.branch ?? "no branch"}</span> ·{" "}
            <span>{run.commit_sha ? run.commit_sha.slice(0, 7) : "no commit"}</span> ·{" "}
            <span>{run.environment ?? "no environment"}</span> ·{" "}
            {run.ci_run_url ? (
              <a href={run.ci_run_url} target="_blank" rel="noreferrer">{run.ci_provider}</a>
            ) : (
              run.ci_provider
            )}
          </p>
          <div className="tiles">
            <div className="card">
              <div className="tile-value">{run.total}</div>
              <div className="tile-label">Results</div>
            </div>
            <div className="card">
              <div className="tile-value">{run.passed}</div>
              <div className="tile-label">Passed</div>
            </div>
            <div className="card">
              <div className="tile-value">{run.failed + run.errored}</div>
              <div className="tile-label">Failed + errored</div>
            </div>
            <div className="card">
              <div className="tile-value">{formatDuration(run.duration_ms)}</div>
              <div className="tile-label">Duration</div>
            </div>
          </div>

          {run.results.length === 0 ? (
            <p className="muted">No {status || ""} results in this run.</p>
          ) : (
            <div className="card">
              <table className="data">
                <thead>
                  <tr>
                    <th>Test</th><th>Status</th><th>Duration</th><th>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {run.results.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <Link to={`/projects/${projectId}/tests/${encodeURIComponent(r.test_key)}`}>
                          {r.name}
                        </Link>
                        <div className="muted">
                          {r.suite} / {r.class_name}
                          {r.truncated && <span> · truncated</span>}
                          {r.redacted && <span> · redacted</span>}
                        </div>
                      </td>
                      <td><StatusDot status={r.status} /></td>
                      <td>{formatDuration(r.duration_ms)}</td>
                      <td><Message text={r.message} /></td>
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
