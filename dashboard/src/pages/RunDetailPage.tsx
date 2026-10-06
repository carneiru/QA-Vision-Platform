import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { RunStatusFilter, getRun, listRuns } from "../api/runs";
import { formatDuration } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FailureGroups from "../components/FailureGroups";
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
  // The run before this one on the same branch: the natural thing to compare with
  const previous = useQuery({
    queryKey: ["runs", Number(projectId), "before", id],
    queryFn: () =>
      listRuns(Number(projectId), { limit: 1, offset: 0, until: run!.started_at, ...(run!.branch ? { branch: run!.branch } : {}) }),
    enabled: run !== undefined,
  });
  const previousRun = previous.data?.[0];

  return (
    <section>
      <p>
        <Link className="link-arrow" to=".." relative="path"><ArrowLeft size={14} aria-hidden="true" /> All runs</Link>
      </p>

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
          {run.components.length > 0 && (
            <p className="muted">
              Under test:{" "}
              {run.components.map((c, i) => (
                <span key={c.name}>
                  {i > 0 && " · "}
                  <code>{c.name}@{c.sha.slice(0, 12)}</code>
                </span>
              ))}
            </p>
          )}
          {(run.commit_author || run.commit_message || run.pr_number || run.base_branch) && (
            <p className="muted">
              {run.commit_author && <span>{run.commit_author}</span>}
              {run.commit_message && <span> · {run.commit_message}</span>}
              {run.pr_number && <span> · PR #{run.pr_number}</span>}
              {run.base_branch && <span> · into {run.base_branch}</span>}
            </p>
          )}
          {previousRun && (
            <p>
              <Link className="link-arrow" to={`compare/${previousRun.id}`}>
                Compare with previous run #{previousRun.id}
              </Link>
            </p>
          )}
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

          {run.failed + run.errored > 0 && <FailureGroups runId={run.id} projectId={projectId} />}

          {run.change_base_ref !== null && (
            <div className="card">
              <h3>Changes</h3>
              <p className="muted">
                {run.changed_files} file(s), +{run.additions ?? 0} −{run.deletions ?? 0} vs {run.change_base_ref}
                {run.changes_truncated && <span> · list truncated at 1000 files</span>}
              </p>
              {run.changes.length > 0 && (
                <table className="data">
                  <thead>
                    <tr>
                      <th>File</th><th>Status</th><th>+</th><th>−</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.changes.map((f) => (
                      <tr key={f.path}>
                        <td>{f.path}</td>
                        <td>{f.status}</td>
                        <td>{f.additions ?? "—"}</td>
                        <td>{f.deletions ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

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

          {run.results.length === 0 ? (
            <p className="muted">No {status || ""} results in this run.</p>
          ) : (
            <div className="card" tabIndex={0} role="region" aria-label="Test results">
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
                          {r.owner && <span> · {r.owner}</span>}
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
