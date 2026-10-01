import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { formatDuration, formatPassRate, getTests } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import StatusDot from "../components/StatusDot";

const PAGE = 50;

export default function TestsPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [days, setDays] = useState(30);
  const [sort, setSort] = useState<"failures" | "duration" | "name">("failures");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  const query = useQuery({
    queryKey: ["tests", id, days, sort, search, offset],
    queryFn: () => getTests(id, { days, sort, search: search || undefined, limit: PAGE, offset }),
    placeholderData: keepPreviousData,
  });

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setSearch(searchInput);
    setOffset(0);
  }

  const rows = query.data ?? [];

  return (
    <section>
      <h2 className="sr-only">Tests</h2>
      <form onSubmit={applyFilters}>
        <FilterBar>
          <label>
            Days
            <select value={days} onChange={(e) => { setDays(Number(e.target.value)); setOffset(0); }}>
              <option value={7}>7</option>
              <option value={30}>30</option>
              <option value={90}>90</option>
            </select>
          </label>
          <label>
            Sort
            <select value={sort} onChange={(e) => { setSort(e.target.value as typeof sort); setOffset(0); }}>
              <option value="failures">Failures</option>
              <option value="duration">Duration</option>
              <option value="name">Name</option>
            </select>
          </label>
          <label>
            Search
            <input value={searchInput} onChange={(e) => setSearchInput(e.target.value)} />
          </label>
          <button type="submit">Apply</button>
        </FilterBar>
      </form>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading tests…</p>}
      {query.data && rows.length === 0 && <p className="muted">No tests in the last {days} days.</p>}

      {rows.length > 0 && (
        <div className="card">
          <table className="data">
            <thead>
              <tr>
                <th>Test</th><th>Runs</th><th>Pass rate</th><th>Failed</th>
                <th>Errored</th><th>Avg duration</th><th>Last status</th><th>Last seen</th>
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
                  <td>{r.runs}</td>
                  <td>{formatPassRate(r.pass_rate)}</td>
                  <td>{r.failed}</td>
                  <td>{r.errored}</td>
                  <td>{formatDuration(r.avg_duration_ms)}</td>
                  <td><StatusDot status={r.last_status} /></td>
                  <td>{new Date(r.last_seen).toLocaleString()}</td>
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
