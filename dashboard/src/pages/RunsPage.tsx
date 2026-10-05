import { FormEvent, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { listRuns, RunFilters } from "../api/runs";
import { formatDuration } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";

const PAGE = 50;

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
  const search = params.toString();
  const applied = readValues(params);
  const filters = toFilters(applied);
  const active = KEYS.filter((k) => applied[k] !== "").length;
  const advancedActive = ADVANCED.filter((k) => applied[k] !== "").length;
  const [form, setForm] = useState<Values>(applied);
  const [offset, setOffset] = useState(0);

  // A pasted link or back/forward changes the URL: the form follows it
  useEffect(() => {
    setForm(readValues(new URLSearchParams(search)));
    setOffset(0);
  }, [search]);

  const query = useQuery({
    queryKey: ["runs", id, filters, offset],
    queryFn: () => listRuns(id, { limit: PAGE, offset, ...filters }),
    placeholderData: keepPreviousData,
  });

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
    setParams(next);
    setOffset(0);
  }

  function clearFilters() {
    setParams(new URLSearchParams());
    setOffset(0);
  }

  const rows = query.data ?? [];

  return (
    <section>
      <h2 className="sr-only">Runs</h2>
      <form onSubmit={applyFilters}>
        <FilterBar>
          <label>
            Status
            <select value={form.status} onChange={(e) => set("status", e.target.value)}>
              <option value="">All</option>
              <option value="failing">With failures</option>
              <option value="passing">All green</option>
            </select>
          </label>
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
            <label>
              CI
              <select value={form.ci_provider} onChange={(e) => set("ci_provider", e.target.value)}>
                <option value="">Any</option>
                {Object.entries(CI_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
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
