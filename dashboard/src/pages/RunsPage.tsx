import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { listRuns } from "../api/runs";
import { formatDuration } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";

const PAGE = 50;

export default function RunsPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [branchInput, setBranchInput] = useState("");
  const [branch, setBranch] = useState("");
  const [offset, setOffset] = useState(0);

  const query = useQuery({
    queryKey: ["runs", id, branch, offset],
    queryFn: () => listRuns(id, { limit: PAGE, offset, branch: branch || undefined }),
    placeholderData: keepPreviousData,
  });

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setBranch(branchInput.trim());
    setOffset(0);
  }

  const rows = query.data ?? [];

  return (
    <section>
      <h2 className="sr-only">Runs</h2>
      <form onSubmit={applyFilters}>
        <FilterBar>
          <label>
            Branch
            <input value={branchInput} onChange={(e) => setBranchInput(e.target.value)} placeholder="all" />
          </label>
          <button type="submit">Apply</button>
        </FilterBar>
      </form>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading runs…</p>}
      {query.data && rows.length === 0 && (
        <p className="muted">No runs{branch && ` on ${branch}`}.</p>
      )}
      {query.data && rows.length === 0 && offset > 0 && (
        <div className="filters">
          <button onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
        </div>
      )}

      {rows.length > 0 && (
        <div className="card" tabIndex={0} role="region" aria-label="Runs">
          <table className="data">
            <thead>
              <tr>
                <th>Run</th><th>Started</th><th>Branch</th><th className="hide-narrow">Commit</th><th className="hide-narrow">Environment</th>
                <th className="hide-narrow">CI</th><th>Passed</th><th>Failed</th><th className="hide-narrow">Errored</th><th className="hide-narrow">Skipped</th><th className="hide-narrow">Duration</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link to={`${r.id}`}>#{r.id}</Link>
                  </td>
                  <td>{new Date(r.started_at).toLocaleString()}</td>
                  <td>{r.branch ?? "—"}</td>
                  <td className="hide-narrow">{r.commit_sha ? r.commit_sha.slice(0, 7) : "—"}</td>
                  <td className="hide-narrow">{r.environment ?? "—"}</td>
                  <td className="hide-narrow">
                    {r.ci_run_url ? (
                      <a href={r.ci_run_url} target="_blank" rel="noreferrer">
                        {r.ci_provider}
                      </a>
                    ) : (
                      r.ci_provider
                    )}
                  </td>
                  <td>{r.passed}</td>
                  <td>{r.failed}</td>
                  <td className="hide-narrow">{r.errored}</td>
                  <td className="hide-narrow">{r.skipped}</td>
                  <td className="hide-narrow">{formatDuration(r.duration_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="filters">
            <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
              Previous
            </button>
            <span className="muted">Rows {offset + 1}–{offset + rows.length}</span>
            <button disabled={rows.length < PAGE} onClick={() => setOffset(offset + PAGE)}>
              Next
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
