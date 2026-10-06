import { FormEvent, useEffect, useId, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowUp, Bot, FileCode, Plus, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Case, CaseInput, PRIORITIES, Priority, STATUSES, CaseStatus, Step, createCase, getCase, parseLabels, updateCase } from "../api/cases";
import { getHistory, getTests } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import GherkinBlock from "../components/GherkinBlock";
import StatusDot from "../components/StatusDot";
import { useCanEdit } from "../lib/useCanEdit";

interface Draft {
  title: string;
  description: string;
  steps: Step[];
  labels: string;
  priority: Priority;
  status: CaseStatus;
}

const EMPTY: Draft = { title: "", description: "", steps: [{ action: "", expected: "" }], labels: "", priority: "medium", status: "draft" };

function toDraft(c: Case): Draft {
  return {
    title: c.title, description: c.description ?? "", steps: c.steps.length ? c.steps : [{ action: "", expected: "" }],
    labels: c.labels.join(", "), priority: c.priority, status: c.status,
  };
}

function toInput(d: Draft): CaseInput {
  return {
    title: d.title.trim(),
    description: d.description.trim() || null,
    steps: d.steps.filter((s) => s.action.trim()).map((s) => ({ action: s.action.trim(), expected: s.expected.trim() })),
    labels: parseLabels(d.labels),
    priority: d.priority,
    status: d.status,
  };
}

/** An imported case's title, steps and labels belong to its .feature file: save only what QA Vision owns. */
function toOwnedInput(d: Draft): CaseInput {
  return { description: d.description.trim() || null, priority: d.priority, status: d.status };
}

/** The automated test a case is linked to: its latest result, or a search to link one. */
function Automation({ projectId, c, canEdit, onLink }: {
  projectId: number;
  c: Case;
  canEdit: boolean;
  onLink: (key: string | null, name?: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [asked, setAsked] = useState("");
  const latest = useQuery({
    queryKey: ["history", projectId, c.automated_test_key, "latest"],
    queryFn: () => getHistory(projectId, c.automated_test_key!, { days: 90, limit: 1 }),
    enabled: c.automated_test_key != null,
  });
  const found = useQuery({
    queryKey: ["tests", projectId, "link", asked],
    queryFn: () => getTests(projectId, { days: 90, sort: "name", search: asked, limit: 10, offset: 0 }),
    enabled: asked !== "",
  });
  const last = latest.data?.executions[0];

  return (
    <section className="card" aria-labelledby="automation">
      <h3 id="automation">Automation</h3>
      {c.automated_test_key ? (
        <>
          <p>
            <span className="linked"><Bot size={16} aria-hidden="true" /> Linked to</span>{" "}
            <Link to={`/projects/${projectId}/tests/${encodeURIComponent(c.automated_test_key)}`}>
              {c.automated_name ?? "the automated test"}
            </Link>
          </p>
          {latest.isPending && <p className="muted">Loading the latest result…</p>}
          {latest.isError && <p className="muted">No result in the last 90 days.</p>}
          {last && (
            <p className="muted">
              Latest result: <StatusDot status={last.status} /> in run #{last.run_id}, {new Date(last.started_at).toLocaleString()}
            </p>
          )}
          {canEdit && <button type="button" onClick={() => onLink(null)}>Unlink</button>}
        </>
      ) : (
        <>
          <p className="muted">Manual. Link the automated test that covers this case to see its latest result here.</p>
          {canEdit && (
            <form className="filters" onSubmit={(e) => { e.preventDefault(); setAsked(search.trim()); }}>
              <label>
                Find an automated test
                <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="test name" />
              </label>
              <button type="submit">Search</button>
            </form>
          )}
          {found.data && found.data.length === 0 && <p className="muted">No automated test matches “{asked}” in the last 90 days.</p>}
          {found.data && found.data.length > 0 && (
            <ul className="pick-list">
              {found.data.map((t) => {
                const name = [t.suite, t.class_name, t.name].filter(Boolean).join(" › ");
                return (
                  <li key={t.test_key}>
                    <span className="wrap-anywhere">{name}</span>
                    <button type="button" aria-label={`Link ${name}`} onClick={() => onLink(t.test_key, name)}>Link</button>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

/** Write a new case, or read and edit one. People who may not edit see it read-only. */
export default function CaseEditorPage() {
  const { projectId, caseNumber } = useParams();
  const id = Number(projectId);
  const number = caseNumber ? Number(caseNumber) : null;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const canEdit = useCanEdit(id) === true;
  const ids = useId();

  const existing = useQuery({
    queryKey: ["case", id, number],
    queryFn: () => getCase(id, number!),
    enabled: number !== null,
  });
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (existing.data) setDraft(toDraft(existing.data));
  }, [existing.data]);

  const save = useMutation({
    mutationFn: (input: CaseInput) => (number === null ? createCase(id, input) : updateCase(id, number, input)),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["cases", id] });
      for (const key of ["case-labels", "case-folders", "case-features", "cases-total"]) {
        qc.invalidateQueries({ queryKey: [key, id] });
      }
      qc.setQueryData(["case", id, c.number], c);
      setSaved(true);
      if (number === null) navigate(`../${c.number}`, { relative: "path", replace: true });
    },
  });

  function setStep(i: number, field: keyof Step, value: string) {
    setDraft((d) => ({ ...d, steps: d.steps.map((s, j) => (j === i ? { ...s, [field]: value } : s)) }));
    setSaved(false);
  }
  function moveStep(i: number, by: number) {
    setDraft((d) => {
      const steps = [...d.steps];
      [steps[i], steps[i + by]] = [steps[i + by], steps[i]];
      return { ...d, steps };
    });
  }
  function change<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
    setSaved(false);
  }
  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate(existing.data?.source_path ? toOwnedInput(draft) : toInput(draft));
  }

  if (number !== null && existing.error != null) {
    return <ErrorBanner error={existing.error} onRetry={() => existing.refetch()} />;
  }
  if (number !== null && existing.isPending) return <p className="muted">Loading the case…</p>;
  const c = existing.data;
  const readOnly = !canEdit;
  const imported = c?.source_path != null;

  return (
    <section>
      <p>
        <Link className="link-arrow" to=".." relative="path">
          <ArrowLeft size={14} aria-hidden="true" /> All test cases
        </Link>
      </p>
      <h2>{c ? `${c.key} · ${c.title}` : "New test case"}</h2>
      {c && c.suites.length > 0 && (
        <p className="muted">
          In suites:{" "}
          {c.suites.map((s, i) => (
            <span key={s.id}>{i > 0 && ", "}<Link to={`../../suites/${s.id}`} relative="path">{s.name}</Link></span>
          ))}
        </p>
      )}

      {c?.source_path && (
        <div className="card source-badge">
          <FileCode size={16} aria-hidden="true" />
          <p>Imported from <code>{c.source_path}</code></p>
          <p className="muted">Title, steps and labels come from the .feature file.</p>
        </div>
      )}

      <form className="card form-stack case-form" onSubmit={onSubmit}>
        <fieldset disabled={readOnly} className="plain-fieldset">
          <label>
            Title
            <input required maxLength={200} readOnly={imported} value={draft.title} onChange={(e) => change("title", e.target.value)} />
          </label>
          <label>
            <span>Preconditions and context <span className="muted">(optional)</span></span>
            <textarea rows={3} maxLength={10000} value={draft.description} onChange={(e) => change("description", e.target.value)} />
          </label>

          {imported ? (
            <>
              <h3>Gherkin</h3>
              <GherkinBlock text={c?.gherkin ?? ""} />
            </>
          ) : (
            <>
          <h3 id={`${ids}-steps`}>Steps</h3>
          <ol className="steps" aria-labelledby={`${ids}-steps`}>
            {draft.steps.map((s, i) => (
              <li key={i} className="step">
                <span className="step-number" aria-hidden="true">{i + 1}</span>
                <div className="step-fields">
                  <label>
                    Action <span className="sr-only">{i + 1}</span>
                    <textarea maxLength={2000} value={s.action} onChange={(e) => setStep(i, "action", e.target.value)} />
                  </label>
                  <label>
                    Expected result <span className="sr-only">{i + 1}</span>
                    <textarea maxLength={2000} value={s.expected} onChange={(e) => setStep(i, "expected", e.target.value)} />
                  </label>
                </div>
                {!readOnly && (
                  <div className="step-actions">
                    <button type="button" className="ghost" aria-label={`Move step ${i + 1} up`} disabled={i === 0} onClick={() => moveStep(i, -1)}>
                      <ArrowUp size={16} aria-hidden="true" />
                    </button>
                    <button type="button" className="ghost" aria-label={`Move step ${i + 1} down`} disabled={i === draft.steps.length - 1} onClick={() => moveStep(i, 1)}>
                      <ArrowDown size={16} aria-hidden="true" />
                    </button>
                    <button type="button" className="ghost" aria-label={`Remove step ${i + 1}`} disabled={draft.steps.length === 1}
                      onClick={() => change("steps", draft.steps.filter((_, j) => j !== i))}>
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ol>
          {!readOnly && draft.steps.length < 50 && (
            <div className="add-step">
              <button type="button" onClick={() => change("steps", [...draft.steps, { action: "", expected: "" }])}>
                <Plus size={16} aria-hidden="true" /> Add step
              </button>
            </div>
          )}

            </>
          )}

          <label>
            <span>Labels <span className="muted">(comma separated)</span></span>
            <input readOnly={imported} value={draft.labels} onChange={(e) => change("labels", e.target.value)} placeholder="e.g. checkout, smoke"
              spellCheck={false} autoComplete="off" />
          </label>
          <div className="filters">
            <label>
              Priority
              <select value={draft.priority} onChange={(e) => change("priority", e.target.value as Priority)}>
                {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
            <label>
              Status
              <select value={draft.status} onChange={(e) => change("status", e.target.value as CaseStatus)}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </div>
        </fieldset>
        {save.error != null && <ErrorBanner error={save.error} />}
        {saved && !save.isPending && <p className="success-note" role="status">Saved.</p>}
        {!readOnly && (
          <div className="button-row">
            <button className="primary" type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : number === null ? "Create case" : "Save changes"}
            </button>
          </div>
        )}
        {readOnly && <p className="muted">Only owners, admins and members can change test cases.</p>}
      </form>

      {c && (
        <Automation
          projectId={id}
          c={c}
          canEdit={canEdit}
          onLink={(key, name) => save.mutate({ automated_test_key: key, ...(key ? { automated_name: name } : {}) })}
        />
      )}
    </section>
  );
}
