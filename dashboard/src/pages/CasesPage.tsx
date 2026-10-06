import { FormEvent, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Bot, Plus } from "lucide-react";
import { CaseStatus, PRIORITIES, Priority, listCases, listLabels } from "../api/cases";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import { useCanEdit } from "../lib/useCanEdit";

const PAGE = 50;
const KEYS = ["q", "label", "status", "priority"] as const;
type Values = Record<(typeof KEYS)[number], string>;

const read = (p: URLSearchParams): Values =>
  Object.fromEntries(KEYS.map((k) => [k, p.get(k) ?? ""])) as Values;

export function Labels({ labels }: { labels: string[] }) {
  if (labels.length === 0) return null;
  return (
    <ul className="chip-list" aria-label="Labels">
      {labels.map((l) => <li key={l} className="chip">{l}</li>)}
    </ul>
  );
}

/** The project's written test cases: search, filter, open, write a new one. */
export default function CasesPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const canEdit = useCanEdit(id);
  const [params, setParams] = useSearchParams();
  const applied = read(params);
  const [form, setForm] = useState<Values>(applied);
  const [offset, setOffset] = useState(0);
  const search = params.toString();
  useEffect(() => {
    setForm(read(new URLSearchParams(search)));
    setOffset(0);
  }, [search]);

  const archived = applied.status === "archived";
  const status = applied.status === "draft" || applied.status === "ready" || archived ? (applied.status as CaseStatus) : undefined;
  const query = useQuery({
    queryKey: ["cases", id, search, offset],
    queryFn: () =>
      listCases(id, {
        search: applied.q || undefined, label: applied.label || undefined, status,
        priority: (PRIORITIES as string[]).includes(applied.priority) ? (applied.priority as Priority) : undefined,
        limit: PAGE, offset,
      }),
    placeholderData: keepPreviousData,
  });
  const labels = useQuery({ queryKey: ["case-labels", id], queryFn: () => listLabels(id) });

  function apply(e: FormEvent) {
    e.preventDefault();
    const next = new URLSearchParams();
    for (const k of KEYS) if (form[k].trim()) next.set(k, form[k].trim());
    setParams(next);
  }

  const data = query.data;
  const filtered = KEYS.some((k) => applied[k] !== "");

  return (
    <section>
      <h2 className="sr-only">Test cases</h2>
      <div className="view-tabs">
        <span aria-current="page">Cases</span>
        <Link to="../suites" relative="path">Suites</Link>
        {canEdit && (
          <Link className="button primary" to="new">
            <Plus size={16} aria-hidden="true" /> New case
          </Link>
        )}
      </div>

      <form onSubmit={apply}>
        <FilterBar>
          <label>
            Search
            <input type="search" value={form.q} onChange={(e) => setForm({ ...form, q: e.target.value })} placeholder="title" />
          </label>
          <label>
            Label
            <select value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })}>
              <option value="">Any</option>
              {(labels.data ?? []).map((l) => (
                <option key={l.label} value={l.label}>{l.label} ({l.count})</option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              <option value="">Draft and ready</option>
              <option value="draft">Draft</option>
              <option value="ready">Ready</option>
              <option value="archived">Archived</option>
            </select>
          </label>
          <label>
            Priority
            <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              <option value="">Any</option>
              {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          <button type="submit">Apply</button>
        </FilterBar>
      </form>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading test cases…</p>}
      {data && data.total === 0 && (
        filtered ? (
          <p className="muted">No test cases match these filters.</p>
        ) : (
          <div className="card empty-state">
            <h3>No test cases yet</h3>
            <p className="muted">
              Write down what to check, step by step, and link each case to the automated test that covers it.
            </p>
            {canEdit && <Link className="button primary" to="new"><Plus size={16} aria-hidden="true" /> Write the first case</Link>}
          </div>
        )
      )}
      {data && data.items.length > 0 && (
        <div className="card" tabIndex={0} role="region" aria-label="Test cases">
          <table className="data">
            <thead>
              <tr>
                <th>Case</th><th>Title</th><th className="hide-narrow">Priority</th><th>Status</th>
                <th className="hide-narrow">Automated</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <tr key={c.number}>
                  <td><Link to={`${c.number}`}>{c.key}</Link></td>
                  <td className="wrap-anywhere">
                    {c.title}
                    <Labels labels={c.labels} />
                  </td>
                  <td className="hide-narrow">{c.priority}</td>
                  <td>{c.status}</td>
                  <td className="hide-narrow">
                    {c.automated_test_key ? (
                      <span className="linked"><Bot size={14} aria-hidden="true" /> Linked</span>
                    ) : (
                      <span className="muted">Manual</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="filters">
            <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
            <span className="muted">{offset + 1}–{offset + data.items.length} of {data.total}</span>
            <button disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>Next</button>
          </div>
        </div>
      )}
    </section>
  );
}
