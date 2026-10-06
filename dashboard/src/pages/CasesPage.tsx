import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Bot, FileCode, Plus, Upload } from "lucide-react";
import {
  CaseStatus, PRIORITIES, Priority, listCases, listFeatures, listLabels, searchCases,
} from "../api/cases";
import { getLatestKeys } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import FilterSelect from "../components/FilterSelect";
import { useCanEdit } from "../lib/useCanEdit";

const PAGE = 50;
const KEYS = ["q", "label", "status", "priority", "origin", "folder", "linked", "result", "feature", "ado"] as const;
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
    queryFn: async () => {
      const base = {
        search: applied.q || undefined, status,
        priority: (PRIORITIES as string[]).includes(applied.priority) ? (applied.priority as Priority) : undefined,
        origin: (applied.origin === "manual" || applied.origin === "imported" ? applied.origin : undefined) as "manual" | "imported" | undefined,
        folder: applied.folder || undefined, feature: applied.feature || undefined, ado: applied.ado || undefined,
        limit: PAGE, offset,
      };
      const linked = applied.linked === "true" || applied.linked === "false" ? applied.linked : undefined;
      if (!applied.result) {
        return { page: await listCases(id, { ...base, label: applied.label || undefined, linked }), resultUnavailable: false };
      }
      let keys: string[];
      try {
        keys = (await getLatestKeys(id, applied.result === "never" ? "any" : (applied.result as "passed" | "failed" | "skipped"))).keys;
      } catch {
        return { page: await listCases(id, { ...base, label: applied.label || undefined, linked }), resultUnavailable: true };
      }
      return {
        page: await searchCases(id, {
          ...base, labels: applied.label ? [applied.label] : [], linked: linked ? linked === "true" : undefined,
          test_keys: keys, keys_mode: applied.result === "never" ? "exclude" : "include",
        }),
        resultUnavailable: false,
      };
    },
    placeholderData: keepPreviousData,
  });
  const labels = useQuery({ queryKey: ["case-labels", id], queryFn: () => listLabels(id) });
  const features = useQuery({ queryKey: ["case-features", id], queryFn: () => listFeatures(id) });
  const labelOptions = useMemo(
    () => (labels.data ?? []).filter((l) => !/^ado-\d+$/.test(l.label)).map((l) => ({ value: l.label, label: `${l.label} (${l.count})` })),
    [labels.data],
  );
  const adoOptions = useMemo(
    () => (labels.data ?? []).flatMap((l) => {
      const m = /^ado-(\d+)$/.exec(l.label);
      return m ? [{ value: m[1], label: `#${m[1]} (${l.count})` }] : [];
    }),
    [labels.data],
  );
  const featureOptions = useMemo(
    () => (features.data ?? []).map((f) => ({ value: f.feature, label: `${f.feature} (${f.count})` })),
    [features.data],
  );

  function apply(e: FormEvent) {
    e.preventDefault();
    const next = new URLSearchParams();
    for (const k of KEYS) if (form[k].trim()) next.set(k, form[k].trim());
    setParams(next);
  }

  const data = query.data?.page;
  const filtered = KEYS.some((k) => applied[k] !== "");

  return (
    <section>
      <h2 className="sr-only">Test cases</h2>
      <div className="view-tabs">
        <span aria-current="page">Cases</span>
        <Link to="../suites" relative="path">Suites</Link>
        {canEdit && (
          <div className="button-row view-tabs-actions">
            <Link className="button" to="import">
              <Upload size={16} aria-hidden="true" /> Import from Gherkin
            </Link>
            <Link className="button primary" to="new">
              <Plus size={16} aria-hidden="true" /> New case
            </Link>
          </div>
        )}
      </div>

      <form onSubmit={apply}>
            <FilterBar>
              <label>
                Search
                <input type="search" value={form.q} onChange={(e) => setForm({ ...form, q: e.target.value })} placeholder="title" />
              </label>
              <FilterSelect label="Label" value={form.label} options={labelOptions} onChange={(v) => setForm({ ...form, label: v })} />
              <FilterSelect label="Status" value={form.status} emptyLabel="Draft and ready" onChange={(v) => setForm({ ...form, status: v })}
                options={[{ value: "draft", label: "Draft" }, { value: "ready", label: "Ready" }, { value: "archived", label: "Archived" }]} />
              <FilterSelect label="Priority" value={form.priority} onChange={(v) => setForm({ ...form, priority: v })}
                options={PRIORITIES.map((p) => ({ value: p, label: p }))} />
              <FilterSelect label="Origin" value={form.origin} emptyLabel="All" onChange={(v) => setForm({ ...form, origin: v })}
                options={[{ value: "manual", label: "Manual" }, { value: "imported", label: "Imported" }]} />
              <FilterSelect label="Link" value={form.linked} onChange={(v) => setForm({ ...form, linked: v })}
                options={[{ value: "true", label: "Linked" }, { value: "false", label: "Not linked" }]} />
              <FilterSelect label="Latest result" value={form.result} onChange={(v) => setForm({ ...form, result: v })}
                options={[{ value: "passed", label: "Passed" }, { value: "failed", label: "Failed" }, { value: "skipped", label: "Skipped" }, { value: "never", label: "Never ran" }]} />
              <FilterSelect label="Feature" value={form.feature} options={featureOptions} onChange={(v) => setForm({ ...form, feature: v })} />
              <FilterSelect label="Azure DevOps" value={form.ado} options={adoOptions} onChange={(v) => setForm({ ...form, ado: v })} />
              <button type="submit">Apply</button>
              <button type="button" onClick={() => setParams(new URLSearchParams())}>Clear filters</button>
            </FilterBar>
          </form>

          {query.data?.resultUnavailable && (
            <p className="error-banner" role="status">Latest result filter unavailable right now; showing the other filters.</p>
          )}
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
                        {c.source_path && <FileCode size={14} aria-label="Imported" role="img" />}{c.source_path && " "}
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
