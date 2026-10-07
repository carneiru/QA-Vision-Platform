import { FormEvent, useEffect, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowUp, X } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SuiteCase, deleteSuite, getSuite, listCases, setSuiteCases, updateSuite } from "../api/cases";
import ConfirmButton from "../components/ConfirmButton";
import RunControl from "../components/RunControl";
import ErrorBanner from "../components/ErrorBanner";
import { useCanEdit } from "../lib/useCanEdit";

/** One suite: its ordered cases, which members can add, remove and reorder, then save. */
export default function SuiteDetailPage() {
  const { projectId, suiteId } = useParams();
  const id = Number(projectId);
  const sid = Number(suiteId);
  const canEdit = useCanEdit(id) === true;
  const qc = useQueryClient();
  const navigate = useNavigate();

  const suite = useQuery({ queryKey: ["suite", id, sid], queryFn: () => getSuite(id, sid) });
  const [cases, setCases] = useState<SuiteCase[]>([]);
  const [dirty, setDirty] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  useEffect(() => {
    if (!suite.data) return;
    setCases(suite.data.cases);
    setName(suite.data.name);
    setDescription(suite.data.description ?? "");
    setDirty(false);
  }, [suite.data]);

  const [search, setSearch] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const found = useQuery({
    queryKey: ["cases", id, "pick", asked],
    queryFn: () => listCases(id, { search: asked || undefined, limit: 20, offset: 0 }),
    enabled: asked !== null,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["suites", id] });
    return qc.invalidateQueries({ queryKey: ["suite", id, sid] });
  };
  const saveCases = useMutation({ mutationFn: () => setSuiteCases(id, sid, cases.map((c) => c.number)), onSuccess: refresh });
  const saveDetails = useMutation({
    mutationFn: () => updateSuite(id, sid, { name: name.trim(), description: description.trim() || null }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => deleteSuite(id, sid),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["suites", id] });
      navigate(`/projects/${id}/suites`);
    },
  });

  function move(i: number, by: number) {
    const next = [...cases];
    [next[i], next[i + by]] = [next[i + by], next[i]];
    setCases(next);
    setDirty(true);
  }

  if (suite.error != null) return <ErrorBanner error={suite.error} onRetry={() => suite.refetch()} />;
  if (suite.isPending) return <p className="muted">Loading the suite…</p>;
  const inSuite = new Set(cases.map((c) => c.number));

  return (
    <section>
      <p>
        <Link className="link-arrow" to=".." relative="path"><ArrowLeft size={14} aria-hidden="true" /> All suites</Link>
      </p>
      <h2>{suite.data.name}</h2>
      {suite.data.description && <p className="muted">{suite.data.description}</p>}
      <RunControl projectId={id} cases={suite.data.cases.map((c) => ({ number: c.number, title: c.title }))}
        selection={{ suite_id: sid }} label="Run suite" />

      <section className="card" aria-labelledby="suite-cases">
        <h3 id="suite-cases">Cases, in order <span className="muted">({cases.length})</span></h3>
        {cases.length === 0 && <p className="muted">No cases yet{canEdit && ": find them below and add them"}.</p>}
        <ol className="ordered-cases">
          {cases.map((c, i) => (
            <li key={c.number}>
              <span className="muted">{i + 1}.</span>
              <Link to={`../../cases/${c.number}`} relative="path">{c.key}</Link>
              <span className="case-title">
                {c.title}
                {c.status === "archived" && <span className="muted"> · archived</span>}
              </span>
              {canEdit && (
                <span className="button-row">
                  <button type="button" className="ghost" aria-label={`Move ${c.key} up`} disabled={i === 0} onClick={() => move(i, -1)}>
                    <ArrowUp size={16} aria-hidden="true" />
                  </button>
                  <button type="button" className="ghost" aria-label={`Move ${c.key} down`} disabled={i === cases.length - 1} onClick={() => move(i, 1)}>
                    <ArrowDown size={16} aria-hidden="true" />
                  </button>
                  <button type="button" className="ghost" aria-label={`Remove ${c.key} from the suite`}
                    onClick={() => { setCases(cases.filter((x) => x.number !== c.number)); setDirty(true); }}>
                    <X size={16} aria-hidden="true" />
                  </button>
                </span>
              )}
            </li>
          ))}
        </ol>
        {saveCases.error != null && <ErrorBanner error={saveCases.error} />}
        {canEdit && (
          <div className="button-row" style={{ marginTop: "var(--space-3)" }}>
            <button className="primary" disabled={!dirty || saveCases.isPending} onClick={() => saveCases.mutate()}>
              {saveCases.isPending ? "Saving…" : dirty ? "Save order and cases" : "Saved"}
            </button>
          </div>
        )}

        {canEdit && (
          <>
            <form className="filters" style={{ marginTop: "var(--space-4)" }} onSubmit={(e: FormEvent) => { e.preventDefault(); setAsked(search.trim()); }}>
              <label>
                Find cases to add
                <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="title, or empty for all" />
              </label>
              <button type="submit">Search</button>
            </form>
            {found.data && found.data.items.length === 0 && <p className="muted">No case matches.</p>}
            {found.data && found.data.items.length > 0 && (
              <ul className="pick-list">
                {found.data.items.map((c) => (
                  <li key={c.number}>
                    <span className="wrap-anywhere">{c.key} · {c.title}</span>
                    <button
                      type="button"
                      aria-label={`Add ${c.key} to the suite`}
                      disabled={inSuite.has(c.number)}
                      onClick={() => {
                        setCases([...cases, { number: c.number, key: c.key, title: c.title, status: c.status, priority: c.priority, labels: c.labels, automated_test_key: c.automated_test_key }]);
                        setDirty(true);
                      }}
                    >
                      {inSuite.has(c.number) ? "In the suite" : "Add"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>

      {canEdit && (
        <form className="card form-stack" onSubmit={(e) => { e.preventDefault(); saveDetails.mutate(); }}>
          <h3>Details</h3>
          <label>
            Name
            <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            <span>Description <span className="muted">(optional)</span></span>
            <input maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          {saveDetails.error != null && <ErrorBanner error={saveDetails.error} />}
          <div className="button-row">
            <button type="submit" disabled={saveDetails.isPending}>{saveDetails.isPending ? "Saving…" : "Save details"}</button>
            <ConfirmButton
              label="Delete suite"
              ariaLabel={`Delete the suite ${suite.data.name}`}
              question="Delete this suite? Its cases stay."
              confirmLabel="Delete"
              onConfirm={() => remove.mutate()}
              disabled={remove.isPending}
            />
          </div>
          {remove.error != null && <ErrorBanner error={remove.error} />}
        </form>
      )}
    </section>
  );
}
