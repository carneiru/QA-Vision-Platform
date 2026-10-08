import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createSuite, listSuites } from "../api/cases";
import ErrorBanner from "../components/ErrorBanner";
import { useCanEdit } from "../lib/useCanEdit";
import PageHeader from "../components/PageHeader";

/** The project's suites: named, ordered lists of test cases. */
export default function SuitesPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const canEdit = useCanEdit(id);
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const suites = useQuery({ queryKey: ["suites", id], queryFn: () => listSuites(id) });
  const create = useMutation({
    mutationFn: () => createSuite(id, { name: name.trim(), ...(description.trim() ? { description: description.trim() } : {}) }),
    onSuccess: () => {
      setName("");
      setDescription("");
      return qc.invalidateQueries({ queryKey: ["suites", id] });
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <section>
      <PageHeader title="Suites" tabs={[{ label: "Cases", to: "../cases" }, { label: "Suites" }]} />

      {suites.error != null && <ErrorBanner error={suites.error} onRetry={() => suites.refetch()} />}
      {suites.isPending && <p className="muted">Loading suites…</p>}
      {suites.data?.length === 0 && (
        <p className="muted">No suites yet. A suite groups cases to run together, such as a smoke check before each deploy.</p>
      )}
      {suites.data != null && suites.data.length > 0 && (
        <div className="card" tabIndex={0} role="region" aria-label="Suites">
          <table className="data">
            <thead>
              <tr><th>Suite</th><th>Cases</th><th className="hide-narrow">Changed</th></tr>
            </thead>
            <tbody>
              {suites.data.map((s) => (
                <tr key={s.id}>
                  <td className="wrap-anywhere">
                    <Link to={`${s.id}`}>{s.name}</Link>
                    {s.description && <div className="muted">{s.description}</div>}
                  </td>
                  <td>{s.case_count}</td>
                  <td className="hide-narrow">{new Date(s.updated_at ?? s.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {canEdit && (
        <form className="card form-stack" onSubmit={onSubmit}>
          <h2>New suite</h2>
          <label>
            Name
            <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Smoke" />
          </label>
          <label>
            <span>Description <span className="muted">(optional)</span></span>
            <input maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          {create.error != null && <ErrorBanner error={create.error} />}
          <div className="button-row">
            <button className="primary" type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create suite"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
