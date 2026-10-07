import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { listRuns, RunFilters } from "../api/runs";
import { formatDuration } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import FilterSelect from "../components/FilterSelect";
import NarrowMeta from "../components/NarrowMeta";
import RunStatusBadge, { runVerdict } from "../components/RunStatusBadge";
import SortableTh from "../components/SortableTh";
import { nextSort, parseSort, sortRows, SortState } from "../lib/sort";
import { LIVE_REFRESH_MS } from "../lib/live";
import { pageOffset, withOffset } from "../lib/useUrlState";

const PAGE = 50;
// The API has no sort parameter for runs: the columns sort the page that is loaded
const SORT_KEYS = ["started", "duration", "failed"] as const;
type SortKey = (typeof SORT_KEYS)[number];
const DEFAULT_SORT: SortState<SortKey> = { key: "started", dir: "desc" };

const CI_LABELS: Record<string, string> = {
  github_actions: "GitHub Actions",
  gitlab_ci: "GitLab CI",
  azure_pipelines: "Azure Pipelines",
  jenkins: "Jenkins",
  other: "Other",
  local: "Local",
};

// URL keys, in URL order. "from" and "to" are local calendar days
// (YYYY-MM-DD); the rest go to the API unchanged.
const KEYS = ["status", "branch", "environment", "ci_provider", "commit", "pr", "author", "from", "to"] as const;
const ADVANCED = ["environment", "ci_provider", "commit", "pr", "author", "from", "to"] as const;
type Key = (typeof KEYS)[number];
type Values = Record<Key, string>;

function readValues(params: URLSearchParams): Values {
  return Object.fromEntries(KEYS.map((k) => [k, params.get(k) ?? ""])) as Values;
}

/** The instant a local calendar day starts, as a UTC ISO string. */
function dayStart(day: string, plusDays = 0): string | undefined {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!m) return undefined;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + plusDays).toISOString();
}

function toFilters(v: Values): RunFilters {
  return {
    status: v.status === "failing" || v.status === "passing" ? v.status : undefined,
    branch: v.branch || undefined,
    environment: v.environment || undefined,
    ci_provider: v.ci_provider || undefined,
    commit: v.commit || undefined,
    pr: v.pr ? Number(v.pr) : undefined,
    author: v.author || undefined,
    since: dayStart(v.from),
    // People read "to" as inclusive, so the API gets the start of the next day
    until: dayStart(v.to, 1),
  };
}

export default function RunsPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [params, setParams] = useSearchParams();
  const filterSearch = withOffset(params, 0).toString();
  const offset = pageOffset(params, PAGE);
  const setOffset = (to: number) => setParams((prev) => withOffset(prev, to));
  const applied = readValues(params);
  const filters = toFilters(applied);
  const sort = parseSort(params.get("sort"), params.get("dir"), SORT_KEYS, DEFAULT_SORT);
  function onSort(key: SortKey) {
    const next = nextSort(sort, key, "desc");
    setParams((prev) => {
      const p = new URLSearchParams(prev);
      if (next.key === DEFAULT_SORT.key && next.dir === DEFAULT_SORT.dir) {
        p.delete("sort");
        p.delete("dir");
      } else {
        p.set("sort", next.key);
        p.set("dir", next.dir);
      }
      return p;
    });
  }
  const active = KEYS.filter((k) => applied[k] !== "").length;
  const advancedActive = ADVANCED.filter((k) => applied[k] !== "").length;
  const [form, setForm] = useState<Values>(applied);

  // A pasted link or back/forward changes the URL: the form follows it
  useEffect(() => {
    setForm(readValues(new URLSearchParams(filterSearch)));
  }, [filterSearch]);

  const query = useQuery({
    queryKey: ["runs", id, filters, offset],
    queryFn: () => listRuns(id, { limit: PAGE, offset, ...filters }),
    placeholderData: keepPreviousData,
    // Only the first page follows new uploads; later pages would shift under the reader
    refetchInterval: offset === 0 ? LIVE_REFRESH_MS : false,
  });

  // Runs that arrived since the first page was last shown, announced once
  const newest = useRef<{ view: string; top: number } | null>(null);
  const [fresh, setFresh] = useState<Set<number>>(new Set());
  const view = `${id}?${filterSearch}`;
  useEffect(() => {
    const data = query.data;
    if (!data || offset !== 0 || query.isPlaceholderData) return;
    const top = data.length > 0 ? data[0].id : 0;
    const seen = newest.current;
    if (seen && seen.view === view && top > seen.top) {
      setFresh(new Set(data.filter((r) => r.id > seen.top).map((r) => r.id)));
    } else if (!seen || seen.view !== view) {
      setFresh(new Set());
    }
    newest.current = { view, top: Math.max(top, seen?.view === view ? seen.top : 0) };
  }, [query.data, query.isPlaceholderData, offset, view]);

  function set(key: Key, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    const next = new URLSearchParams();
    for (const k of KEYS) {
      const value = form[k].trim();
      if (value) next.set(k, value);
    }
    keepSort(next);
    setParams(next);
  }

  /** Filters change which runs load; the chosen order stays */
  function keepSort(next: URLSearchParams) {
    for (const k of ["sort", "dir"]) {
      const v = params.get(k);
      if (v) next.set(k, v);
    }
  }

  function clearFilters() {
    const next = new URLSearchParams();
    keepSort(next);
    setParams(next);
  }

  const rows = sortRows(query.data ?? [], sort, (r, key) =>
    key === "started" ? Date.parse(r.started_at) : key === "duration" ? r.duration_ms : r.failed);

  return (
    <section>
      <h2 className="sr-only">Runs</h2>
      <div className="view-tabs">
        <span aria-current="page">Runs</span>
        <Link to="requested">Requested runs</Link>
      </div>
      <form onSubmit={applyFilters}>
        <FilterBar>
          <FilterSelect label="Status" value={form.status} emptyLabel="All" onChange={(v) => set("status", v)}
            options={[{ value: "failing", label: "With failures" }, { value: "passing", label: "All green" }]} />
          <label>
            Branch
            <input value={form.branch} onChange={(e) => set("branch", e.target.value)} placeholder="all" />
          </label>
          <button type="submit" className="primary">Apply</button>
          {active > 0 && (
            <button type="button" className="ghost" onClick={clearFilters}>
              Clear filters
            </button>
          )}
        </FilterBar>
        <details className="more-filters" open={advancedActive > 0 || undefined}>
          <summary><ChevronRight size={14} aria-hidden="true" className="chevron" /> More filters{advancedActive > 0 && ` (${advancedActive} active)`}</summary>
          <FilterBar>
            <label>
              Environment
              <input value={form.environment} onChange={(e) => set("environment", e.target.value)} maxLength={100} />
            </label>
            <FilterSelect label="CI" value={form.ci_provider} onChange={(v) => set("ci_provider", v)}
              options={Object.entries(CI_LABELS).map(([value, label]) => ({ value, label }))} />
            <label>
              Commit
              <input
                value={form.commit}
                onChange={(e) => set("commit", e.target.value)}
                pattern="[0-9a-fA-F]{4,40}"
                title="At least 4 characters of the commit hash"
                spellCheck={false}
                autoComplete="off"
              />
            </label>
            <label>
              Pull request
              <input type="number" min={1} inputMode="numeric" value={form.pr} onChange={(e) => set("pr", e.target.value)} />
            </label>
            <label>
              Author
              <input value={form.author} onChange={(e) => set("author", e.target.value)} maxLength={255} />
            </label>
            <label>
              From
              <input type="date" value={form.from} max={form.to || undefined} onChange={(e) => set("from", e.target.value)} />
            </label>
            <label>
              To
              <input type="date" value={form.to} min={form.from || undefined} onChange={(e) => set("to", e.target.value)} />
            </label>
          </FilterBar>
        </details>
      </form>

      <p role="status" className="muted live-note">
        {fresh.size > 0 && `${fresh.size} new run${fresh.size === 1 ? "" : "s"}`}
      </p>
      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading runs…</p>}
      {query.data && rows.length === 0 && (
        offset > 0 ? (
          <p className="muted">No runs on this page.</p>
        ) : active > 0 ? (
          <p className="muted">No runs match these filters.</p>
        ) : (
          <p className="muted">No runs yet.</p>
        )
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
                <th>Run</th><th className="hide-narrow">Status</th>
                <SortableTh label="Started" sortKey="started" sort={sort} onSort={onSort} />
                <th>Branch</th><th className="hide-narrow">Commit</th><th className="hide-narrow">Environment</th>
                <th className="hide-narrow">CI</th><th>Passed</th><SortableTh label="Failed" sortKey="failed" sort={sort} onSort={onSort} /><th className="hide-narrow">Errored</th><th className="hide-narrow">Skipped</th><SortableTh label="Duration" sortKey="duration" sort={sort} onSort={onSort} className="hide-narrow" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className={fresh.has(r.id) ? "row-new" : undefined}>
                  <td>
                    <Link to={`${r.id}`}>#{r.id}</Link>
                    <NarrowMeta items={[
                      { label: "Status", value: <RunStatusBadge verdict={runVerdict(r)} /> },
                      { label: "Commit", value: r.commit_sha ? r.commit_sha.slice(0, 7) : "—" },
                      { label: "Environment", value: r.environment ?? "—" },
                      { label: "CI", value: CI_LABELS[r.ci_provider] ?? r.ci_provider },
                      { label: "Errored", value: r.errored },
                      { label: "Skipped", value: r.skipped },
                      { label: "Duration", value: formatDuration(r.duration_ms) },
                    ]} />
                  </td>
                  <td className="hide-narrow"><RunStatusBadge verdict={runVerdict(r)} /></td>
                  <td>{new Date(r.started_at).toLocaleString()}</td>
                  <td>{r.branch ?? "—"}</td>
                  <td className="hide-narrow">{r.commit_sha ? r.commit_sha.slice(0, 7) : "—"}</td>
                  <td className="hide-narrow">{r.environment ?? "—"}</td>
                  <td className="hide-narrow">
                    {r.ci_run_url ? (
                      <a href={r.ci_run_url} target="_blank" rel="noreferrer">
                        {CI_LABELS[r.ci_provider] ?? r.ci_provider}
                      </a>
                    ) : (
                      CI_LABELS[r.ci_provider] ?? r.ci_provider
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
