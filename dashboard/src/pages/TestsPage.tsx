import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { formatDuration, formatPassRate, getTests } from "../api/analytics";
import { downloadCsv, toCsv } from "../lib/csv";
import { fetchAllTests } from "../lib/exportData";
import ErrorBanner from "../components/ErrorBanner";
import NarrowMeta from "../components/NarrowMeta";
import FilterBar from "../components/FilterBar";
import StatusDot from "../components/StatusDot";
import { oneOf, useDraft, useUrlState } from "../lib/useUrlState";

const PAGE = 50;
const DEFAULTS = { days: "30", sort: "failures", search: "" } as const;
const DAYS = ["7", "30", "90"] as const;
const SORTS = ["failures", "duration", "name"] as const;

export default function TestsPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const { values, offset, update, setOffset } = useUrlState(DEFAULTS, PAGE);
  const days = Number(oneOf(values.days, DAYS, "30"));
  const sort = oneOf(values.sort, SORTS, "failures");
  const search = values.search;
  // The text box is a draft until Apply (per-keystroke requests hit the shared rate limit)
  const [searchInput, setSearchInput, commitSearch] = useDraft(search);

  // One extra row tells whether another page exists, so an exact multiple of the page size ends cleanly
  const query = useQuery({
    queryKey: ["tests", id, days, sort, search, offset],
    queryFn: () => getTests(id, { days, sort, search: search || undefined, limit: PAGE + 1, offset }),
    placeholderData: keepPreviousData,
  });

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    update({ search: commitSearch((raw) => raw.trim()) });
  }

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<unknown>(null);

  async function onExport() {
    setExporting(true);
    setExportError(null);
    try {
      const all = await fetchAllTests(id, { days, sort, search: search || undefined });
      const csv = toCsv(
        ["test_key", "suite", "class_name", "name", "runs", "passed", "failed", "errored",
         "skipped", "pass_rate", "avg_duration_ms", "last_status", "last_seen"],
        all.map((r) => [r.test_key, r.suite, r.class_name, r.name, r.runs, r.passed, r.failed,
          r.errored, r.skipped, r.pass_rate, r.avg_duration_ms, r.last_status, r.last_seen]),
      );
      downloadCsv(`tests-project-${id}-${days}d.csv`, csv);
    } catch (err) {
      setExportError(err);
    } finally {
      setExporting(false);
    }
  }

  const fetched = query.data ?? [];
  const rows = fetched.slice(0, PAGE);
  const hasMore = fetched.length > PAGE;

  return (
    <section>
      <h2 className="sr-only">Tests</h2>
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
            Sort
            <select value={sort} onChange={(e) => update({ sort: e.target.value })}>
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
          <button type="button" onClick={onExport} disabled={exporting}>
            {exporting ? "Exporting…" : "Export CSV"}
          </button>
        </FilterBar>
      </form>

      {exportError != null && <ErrorBanner error={exportError} onRetry={onExport} />}
      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading tests…</p>}
      {query.data && rows.length === 0 && (
        <p className="muted">
          {offset > 0 ? "No tests on this page." : search ? `No tests match "${search}" in the last ${days} days.` : `No tests in the last ${days} days.`}
        </p>
      )}
      {query.data && rows.length === 0 && offset > 0 && (
        <div className="filters">
          <button onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
        </div>
      )}

      {rows.length > 0 && (
        <div className="card" tabIndex={0} role="region" aria-label="Tests">
          <table className="data">
            <thead>
              <tr>
                <th>Test</th><th className="hide-narrow">Runs</th><th>Pass rate</th><th>Failed</th>
                <th className="hide-narrow">Errored</th><th className="hide-narrow">Avg duration</th><th>Last status</th><th className="hide-narrow">Last seen</th>
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
                    <NarrowMeta items={[
                      { label: "Runs", value: r.runs },
                      { label: "Errored", value: r.errored },
                      { label: "Avg duration", value: formatDuration(r.avg_duration_ms) },
                      { label: "Last seen", value: new Date(r.last_seen).toLocaleString() },
                    ]} />
                  </td>
                  <td className="hide-narrow">{r.runs}</td>
                  <td>{formatPassRate(r.pass_rate)}</td>
                  <td>{r.failed}</td>
                  <td className="hide-narrow">{r.errored}</td>
                  <td className="hide-narrow">{formatDuration(r.avg_duration_ms)}</td>
                  <td><StatusDot status={r.last_status} /></td>
                  <td className="hide-narrow">{new Date(r.last_seen).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="filters">
            <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
              Previous
            </button>
            <span className="muted">Rows {offset + 1}–{offset + rows.length}</span>
            <button disabled={!hasMore} onClick={() => setOffset(offset + PAGE)}>
              Next
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
