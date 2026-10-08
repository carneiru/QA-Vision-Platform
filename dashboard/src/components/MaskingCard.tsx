import { FormEvent, useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addMaskingPattern,
  listMaskingPatterns,
  previewMaskingPattern,
  removeMaskingPattern,
} from "../api/masking";
import ConfirmButton from "./ConfirmButton";
import ErrorBanner from "./ErrorBanner";

interface Props {
  projectId: number;
  /** Undefined while the role is loading: the list shows, the controls wait. */
  canEdit: boolean | undefined;
}

export default function MaskingCard({ projectId, canEdit }: Props) {
  const qc = useQueryClient();
  const queryKey = ["masking-patterns", projectId];
  const [name, setName] = useState("");
  const [pattern, setPattern] = useState("");
  const [sample, setSample] = useState("");
  const nameHint = useId();
  const patternHint = useId();

  const patterns = useQuery({ queryKey, queryFn: () => listMaskingPatterns(projectId) });
  const add = useMutation({
    mutationFn: () => addMaskingPattern(projectId, name.trim(), pattern),
    onSuccess: () => {
      setName("");
      setPattern("");
      setSample("");
      preview.reset();
      return qc.invalidateQueries({ queryKey });
    },
  });
  const preview = useMutation({
    mutationFn: () => previewMaskingPattern(projectId, name.trim(), pattern, sample),
  });
  const remove = useMutation({
    mutationFn: (id: number) => removeMaskingPattern(projectId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    add.mutate();
  }

  return (
    <div className="card">
      <h2>Masking</h2>
      <p className="muted">
        Before results are stored, passwords, tokens, keys, emails and card numbers in failure
        messages are replaced with <code>[REDACTED:kind]</code>. Add patterns for what only this
        project knows is sensitive, such as customer or account numbers. They apply to results
        sent from now on.
      </p>

      {patterns.error != null && <ErrorBanner error={patterns.error} onRetry={() => patterns.refetch()} />}
      {patterns.isPending && <p className="muted">Loading patterns…</p>}
      {patterns.data?.length === 0 && <p className="muted">This project has no patterns of its own.</p>}
      {patterns.data != null && patterns.data.length > 0 && (
        <table className="data">
          <thead>
            <tr>
              <th>Name</th>
              <th>Pattern</th>
              {canEdit && <th><span className="sr-only">Actions</span></th>}
            </tr>
          </thead>
          <tbody>
            {patterns.data.map((p) => (
              <tr key={p.id}>
                <td><code>{p.name}</code></td>
                <td className="wrap-anywhere"><code>{p.pattern}</code></td>
                {canEdit && (
                  <td className="row-actions">
                    <ConfirmButton
                      label="Remove"
                      ariaLabel={`Remove pattern ${p.name}`}
                      question={`Remove ${p.name}? New results stop being masked by it; results already stored stay as they are.`}
                      confirmLabel="Remove"
                      onConfirm={() => remove.mutate(p.id)}
                      disabled={remove.isPending}
                    />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {remove.error != null && <ErrorBanner error={remove.error} />}

      {canEdit === false && (
        <p className="muted">Only owners, admins and members can add or remove patterns.</p>
      )}
      {canEdit && (
        <form className="form-stack masking-form" onSubmit={onSubmit}>
          <h4>Add a pattern</h4>
          <label>
            Name
            <input
              required
              maxLength={32}
              autoComplete="off"
              spellCheck={false}
              placeholder="customer_id"
              aria-describedby={nameHint}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <span id={nameHint} className="muted field-hint">
              Shown in the marker, e.g. <code>[REDACTED:customer_id]</code>. Lowercase letters, digits, underscores.
            </span>
          </label>
          <label>
            Pattern
            <input
              required
              maxLength={256}
              autoComplete="off"
              spellCheck={false}
              className="mono"
              placeholder="CUST-\d{6}"
              aria-describedby={patternHint}
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
            />
            <span id={patternHint} className="muted field-hint">
              A regular expression in RE2 syntax: no backreferences or lookarounds.
            </span>
          </label>
          <label>
            <span>
              Sample text <span className="muted">(optional, never saved)</span>
            </span>
            <textarea
              rows={2}
              spellCheck={false}
              placeholder="Paste a failure message to try the pattern on"
              value={sample}
              onChange={(e) => setSample(e.target.value)}
            />
          </label>
          {preview.data != null && (
            <div role="status" className="preview-result">
              <span className="muted">
                Stored as ({preview.data.matches === 1 ? "1 match" : `${preview.data.matches} matches`} for
                this pattern):
              </span>
              <pre className="code-block" tabIndex={0} aria-label="Masked preview"><code>{preview.data.masked}</code></pre>
            </div>
          )}
          {preview.error != null && <ErrorBanner error={preview.error} />}
          {add.error != null && <ErrorBanner error={add.error} />}
          <div className="button-row">
            <button
              type="button"
              onClick={() => preview.mutate()}
              disabled={preview.isPending || !name.trim() || !pattern || !sample}
            >
              {preview.isPending ? "Previewing…" : "Preview"}
            </button>
            <button type="submit" disabled={add.isPending}>
              {add.isPending ? "Adding…" : "Add pattern"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
