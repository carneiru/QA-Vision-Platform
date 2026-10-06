import { DragEvent, useId, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, TriangleAlert, Upload } from "lucide-react";
import { ImportAction, ImportFile, ImportResult, importCases } from "../api/cases";
import { ApiError } from "../api/http";
import ErrorBanner from "../components/ErrorBanner";
import { useCanEdit } from "../lib/useCanEdit";

const SUMMARY: { key: keyof ImportResult["summary"]; action: ImportAction; label: string }[] = [
  { key: "created", action: "create", label: "Created" },
  { key: "updated", action: "update", label: "Updated" },
  { key: "moved", action: "move", label: "Moved" },
  { key: "reactivated", action: "reactivate", label: "Reactivated" },
  { key: "archived", action: "archive", label: "Archived" },
  { key: "unchanged", action: "unchanged", label: "Unchanged" },
  { key: "skipped", action: "skip", label: "Skipped" },
];

const withPrefix = (prefix: string, path: string) => prefix.replace(/\/?$/, prefix ? "/" : "") + path;

const readText = (f: File): Promise<string> =>
  typeof f.text === "function"
    ? f.text()
    : new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsText(f);
      });

async function readFeatures(files: File[]): Promise<ImportFile[]> {
  const features = files.filter((f) => f.name.endsWith(".feature"));
  return Promise.all(
    features.map(async (f) => ({
      path: (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name,
      content: await readText(f),
    })),
  );
}

/** Walks a dropped folder (or file) entry into Files; browsers without entries fall back to dataTransfer.files. */
async function filesFromDrop(e: DragEvent): Promise<File[]> {
  const entries = Array.from(e.dataTransfer.items ?? [])
    .map((i) => i.webkitGetAsEntry?.())
    .filter((entry): entry is FileSystemEntry => Boolean(entry));
  if (entries.length === 0) return Array.from(e.dataTransfer.files);
  const out: File[] = [];
  async function walk(entry: FileSystemEntry, dir: string): Promise<void> {
    if (entry.isFile) {
      const file: File = await new Promise((res, rej) => (entry as FileSystemFileEntry).file(res, rej));
      Object.defineProperty(file, "webkitRelativePath", { value: dir + file.name });
      out.push(file);
    } else if (entry.isDirectory) {
      const reader = (entry as FileSystemDirectoryEntry).createReader();
      for (;;) {
        const batch: FileSystemEntry[] = await new Promise((res, rej) => reader.readEntries(res, rej));
        if (batch.length === 0) break;
        for (const child of batch) await walk(child, `${dir}${entry.name}/`);
      }
    }
  }
  for (const entry of entries) await walk(entry, "");
  return out;
}

/** Import Gherkin scenarios as cases: choose files, preview the plan, apply exactly that plan. */
export default function CaseImportPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const canEdit = useCanEdit(id);
  const queryClient = useQueryClient();
  const ids = useId();
  const [files, setFiles] = useState<ImportFile[]>([]);
  const [prefix, setPrefix] = useState("");
  // full=true: the chosen folder is the whole suite, so cases of missing files are archived (ADR-023)
  const [full, setFull] = useState(false);
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [changed, setChanged] = useState(false);
  const [filter, setFilter] = useState<ImportAction | null>(null);
  const [over, setOver] = useState(false);

  const request = () => files.map((f) => ({ ...f, path: withPrefix(prefix, f.path) }));

  const previewIt = useMutation({
    mutationFn: () => importCases(id, request(), { dryRun: true, full }),
    onSuccess: (data) => {
      setPreview(data);
      setFilter(null);
    },
  });
  const apply = useMutation({
    mutationFn: ({ hash, allow }: { hash: string; allow: boolean }) =>
      importCases(id, request(), { dryRun: false, full, expectedPlanHash: hash, allowMassArchive: allow }),
    onSuccess: (data) => {
      setResult(data);
      setPreview(null);
      setChanged(false);
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      void queryClient.invalidateQueries({ queryKey: ["case-labels"] });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409 && err.code === "plan_changed") {
        setChanged(true);
        previewIt.mutate();
      }
    },
  });

  async function choose(picked: File[]) {
    setFiles(await readFeatures(picked));
    setPreview(null);
    setResult(null);
    setChanged(false);
    previewIt.reset();
    apply.reset();
  }

  if (canEdit === undefined) return <p className="muted">Loading…</p>;
  if (!canEdit) {
    return (
      <section>
        <h2>Import from Gherkin</h2>
        <p className="muted">Only editors can import cases. Ask a project member or admin.</p>
      </section>
    );
  }

  const count = preview
    ? preview.summary.created + preview.summary.updated + preview.summary.moved + preview.summary.reactivated + preview.summary.archived
    : 0;
  const archived = preview?.summary.archived ?? 0;
  // Imported cases that are live today: every one of them is in a full plan as unchanged, updated, moved or archived
  const live = preview ? archived + preview.summary.unchanged + preview.summary.updated + preview.summary.moved : 0;
  // The server decides (same rule it enforces on apply); the page only shows it
  const massArchive = preview?.summary.mass_archive ?? false;
  const rows = preview?.items.filter((i) => (filter ? i.action === filter : i.action !== "unchanged")) ?? [];
  const planChanged = apply.error instanceof ApiError && apply.error.code === "plan_changed";
  const error = previewIt.error ?? (planChanged ? null : apply.error);

  return (
    <section>
      <Link className="link-arrow" to=".." relative="path">Back to cases</Link>
      <h2>Import from Gherkin</h2>
      <p className="muted">
        Each scenario in your .feature files becomes a read-only test case. Preview the changes first; nothing is written until you import.
      </p>

      <div className="card form-stack">
        <div
          className={`drop-zone${over ? " over" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={async (e) => {
            e.preventDefault();
            setOver(false);
            await choose(await filesFromDrop(e));
          }}
        >
          <Upload size={24} aria-hidden="true" />
          <p>Drop a folder or .feature files here, or choose them</p>
          <div className="button-row">
            <label className="button file-pick">
              <FolderOpen size={16} aria-hidden="true" /> Choose folder
              <input
                type="file"
                multiple
                aria-label="Choose folder"
                {...{ webkitdirectory: "" }}
                onChange={(e) => {
                  void choose(Array.from(e.target.files ?? []));
                  e.target.value = "";
                }}
              />
            </label>
            <label className="button file-pick">
              Choose files
              <input
                type="file"
                accept=".feature"
                multiple
                aria-label="Choose files"
                onChange={(e) => {
                  void choose(Array.from(e.target.files ?? []));
                  e.target.value = "";
                }}
              />
            </label>
          </div>
          <p role="status" className="muted">
            {files.length} .feature file{files.length === 1 ? "" : "s"} found
          </p>
        </div>

        <div className="check-field">
          <label className="check">
            <input
              type="checkbox"
              checked={full}
              aria-describedby={`${ids}-full-hint`}
              onChange={(e) => {
                setFull(e.target.checked);
                setPreview(null);
                setResult(null);
                setChanged(false);
                apply.reset();
              }}
            />
            This is my complete features folder
          </label>
          <span id={`${ids}-full-hint`} className="muted field-hint">
            {full
              ? "Cases whose .feature file is not in this folder are archived, and renamed files keep their case numbers. Check the preview before importing."
              : "Off: only the files you choose are compared, so cases of a deleted or renamed .feature file are left as they are, and a renamed file's scenarios are created again."}
          </span>
        </div>

        <label>
          Path prefix
          <input
            value={prefix}
            onChange={(e) => {
              setPrefix(e.target.value);
              setPreview(null);
            }}
            aria-describedby={`${ids}-hint`}
            placeholder="tests/"
          />
          <span id={`${ids}-hint`} className="muted">
            Paths must match what your runner reports, e.g. <code>tests/</code> when you chose <code>features/</code>
          </span>
        </label>
        <div className="filters">
          <button
            type="button"
            className="primary"
            disabled={files.length === 0 || previewIt.isPending}
            onClick={() => {
              setResult(null);
              setChanged(false);
              apply.reset();
              previewIt.mutate();
            }}
          >
            {previewIt.isPending ? "Previewing…" : "Preview"}
          </button>
        </div>
      </div>

      {error != null && <ErrorBanner error={error} />}
      {changed && preview && (
        <p className="error-banner" role="status">
          Something changed since your preview. Review the new plan below.
        </p>
      )}

      {result && (
        <div className="card">
          <p className="success-note" role="status">
            Imported: {result.summary.created} created, {result.summary.updated} updated, {result.summary.moved} moved,{" "}
            {result.summary.reactivated} reactivated, {result.summary.archived} archived.
          </p>
          <Link className="button" to="../?origin=imported" relative="path">View imported cases</Link>
        </div>
      )}

      {preview && (
        <div className="card">
          <div className="summary-row" role="group" aria-label="Filter by action">
            {SUMMARY.map((s) => (
              <button
                key={s.key}
                type="button"
                aria-pressed={filter === s.action}
                onClick={() => setFilter(filter === s.action ? null : s.action)}
              >
                {s.label} {preview.summary[s.key]}
              </button>
            ))}
          </div>
          {preview.errors.length > 0 && (
            <div className="error-banner" role="alert">
              <ul className="import-issues">
                {preview.errors.map((er, i) => (
                  <li key={i}>
                    {er.path}
                    {er.line != null ? `:${er.line}` : ""} {er.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {preview.warnings.length > 0 && (
            <ul className="import-issues muted">
              {preview.warnings.map((w, i) => (
                <li key={i}>
                  {w.path}
                  {w.line != null ? `:${w.line}` : ""} {w.message}
                </li>
              ))}
            </ul>
          )}
          {massArchive && (
            <div className="error-banner" role="alert" aria-label="Archive warning">
              <TriangleAlert size={18} aria-hidden="true" />
              <span>
                This archives {archived} of {live} imported cases. Make sure you chose the whole features folder, with the
                right path prefix.
              </span>
            </div>
          )}
          {rows.length === 0 ? (
            <p className="muted">Nothing to show for this filter.</p>
          ) : (
            <div tabIndex={0} role="region" aria-label="Import plan">
              <table className="data">
                <thead>
                  <tr><th>Action</th><th>Scenario</th><th className="hide-narrow">File</th><th>Case</th></tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>
                      <td>{r.action}</td>
                      <td className="wrap-anywhere">{r.scenario ?? <span className="muted">(file)</span>}</td>
                      <td className="hide-narrow wrap-anywhere">{r.path}</td>
                      <td>
                        {r.case_number != null ? <Link to={`../${r.case_number}`} relative="path">TC-{r.case_number}</Link> : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="filters">
            <button
              type="button"
              className="primary"
              disabled={count === 0 || apply.isPending || previewIt.isPending}
              onClick={() => apply.mutate({ hash: preview.plan_hash, allow: massArchive })}
            >
              {apply.isPending ? "Importing…" : `Import ${count} changes${archived > 0 ? ` (archives ${archived})` : ""}`}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
