import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { formatPassRate, getFlaky, muteFlaky, unmuteFlaky } from "../api/analytics";
import { downloadCsv, toCsv } from "../lib/csv";
import ConfirmButton from "../components/ConfirmButton";
import ErrorBanner from "../components/ErrorBanner";
import NarrowMeta from "../components/NarrowMeta";
import FilterBar from "../components/FilterBar";
import SortableTh from "../components/SortableTh";
import StatusDot from "../components/StatusDot";
import { nextSort, parseSort, sortRows, SortState } from "../lib/sort";
import { oneOf, useDraft, useUrlState } from "../lib/useUrlState";

const UNDO_MS = 8000;
const DEFAULTS = { window: "14", min_runs: "5", min_flip: "0.3", branch: "", muted: "", sort: "", dir: "" } as const;
// The flaky endpoint returns every match (confirmed first, then by flip rate), so sorting the loaded rows sorts them all
const SORT_KEYS = ["rate", "seen"] as const;
type SortKey = (typeof SORT_KEYS)[number];
const DEFAULT_SORT: SortState<SortKey> = { key: "rate", dir: "desc" };
const isSortKey = (v: string): v is SortKey => (SORT_KEYS as readonly string[]).includes(v);
const WINDOWS = ["7", "14", "30", "90"] as const;
const clampRuns = (raw: string) => Math.min(1000, Math.max(2, Math.round(Number(raw) || 0)));
const clampRate = (raw: string) => Math.min(1, Math.max(0, Number(raw) || 0));

export default function FlakyPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const { values, update } = useUrlState(DEFAULTS, 1);
  const windowDays = Number(oneOf(values.window, WINDOWS, "14"));
  // Clamped to the API's bounds (min_runs ge=2, min_flip_rate 0..1) so a hand-edited URL never sends an invalid value.
  const minRuns = clampRuns(values.min_runs);
  const minFlipRate = clampRate(values.min_flip);
  const branch = values.branch;
  // Until a header is clicked the rows keep the server's order
  const sort = isSortKey(values.sort) ? parseSort(values.sort, values.dir, SORT_KEYS, DEFAULT_SORT) : null;
  const onSort = (key: SortKey) => {
    const next = sort ? nextSort(sort, key, "desc") : { key, dir: "desc" as const };
    update({ sort: next.key, dir: next.dir });
  };
  const showMuted = values.muted === "1";
  // Drafts apply on submit
  const [minRunsInput, setMinRunsInput, commitRuns] = useDraft(String(minRuns));
  const [minFlipRateInput, setMinFlipRateInput, commitRate] = useDraft(String(minFlipRate));
  const [branchInput, setBranchInput, commitBranch] = useDraft(branch);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    update({
      min_runs: commitRuns((raw) => String(clampRuns(raw))),
      min_flip: commitRate((raw) => String(clampRate(raw))),
      branch: commitBranch((raw) => raw.trim()),
    });
  }

  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["flaky", id, windowDays, minRuns, minFlipRate, branch, showMuted],
    queryFn: () =>
      getFlaky(id, {
        windowDays, minRuns, minFlipRate,
        branch: branch || undefined,
        includeMuted: showMuted || undefined,
      }),
  });

  // Pending and failed are tracked per test key, so quick changes on different rows do not clobber each other
  const [pending, setPending] = useState<ReadonlySet<string>>(new Set());
  const [failed, setFailed] = useState<ReadonlySet<string>>(new Set());
  const withKey = (set: ReadonlySet<string>, key: string, on: boolean) => {
    const next = new Set(set);
    if (on) next.add(key);
    else next.delete(key);
    return next;
  };
  async function change(testKey: string, muted: boolean): Promise<boolean> {
    setPending((p) => withKey(p, testKey, true));
    setFailed((f) => withKey(f, testKey, false));
    try {
      await (muted ? unmuteFlaky(id, testKey) : muteFlaky(id, testKey));
      return true;
    } catch {
      setFailed((f) => withKey(f, testKey, true));
      return false;
    } finally {
      setPending((p) => withKey(p, testKey, false));
      void queryClient.invalidateQueries({ queryKey: ["flaky", id] });
    }
  }

  // Undo is offered for a few seconds after a change, in the status line
  const [undo, setUndo] = useState<{ testKey: string; name: string; muted: boolean } | null>(null);
  useEffect(() => {
    if (!undo) return;
    const timer = setTimeout(() => setUndo(null), UNDO_MS);
    return () => clearTimeout(timer);
  }, [undo]);

  const loaded = query.data ?? [];
  const rows = sort ? sortRows(loaded, sort, (r, key) => (key === "rate" ? r.flip_rate : Date.parse(r.last_seen))) : loaded;
  const toggle = async (testKey: string, name: string, muted: boolean) => {
    if (await change(testKey, muted)) setUndo({ testKey, name, muted: !muted });
  };

  function onExport() {
    // The flaky endpoint returns the full result set, so the loaded rows are everything.
    const csv = toCsv(
      ["test_key", "suite", "class_name", "name", "reason", "flips", "flip_rate", "runs",
       "last_status", "last_seen", "commits"],
      rows.map((r) => [r.test_key, r.suite, r.class_name, r.name, r.reason, r.flips,
        r.flip_rate, r.runs, r.last_status, r.last_seen,
        r.commits.map((c) => (c.environment ? `${c.commit_sha}:${c.environment}` : c.commit_sha)).join("; ")]),
    );
    downloadCsv(`flaky-project-${id}-${windowDays}d.csv`, csv);
  }

  return (
    <section>
      <h2 className="sr-only">Flaky tests</h2>
      <form onSubmit={applyFilters}>
        <FilterBar>
          <label>
            Window (days)
            <select value={String(windowDays)} onChange={(e) => update({ window: e.target.value })}>
              <option value={7}>7</option>
              <option value={14}>14</option>
              <option value={30}>30</option>
              <option value={90}>90</option>
            </select>
          </label>
          <label>
            Min runs
            <input
              type="number" min={2} max={1000} value={minRunsInput}
              onChange={(e) => setMinRunsInput(e.target.value)}
            />
          </label>
          <label>
            Min flip rate
            <input
              type="number" min={0} max={1} step={0.05} value={minFlipRateInput}
              onChange={(e) => setMinFlipRateInput(e.target.value)}
            />
          </label>
          <label>
            Branch
            <input value={branchInput} onChange={(e) => setBranchInput(e.target.value)} placeholder="all" />
          </label>
          <button type="submit">Apply</button>
          <button type="button" onClick={onExport} disabled={rows.length === 0}>
            Export CSV
          </button>
          <label className="check">
            <input
              type="checkbox"
              checked={showMuted}
              onChange={(e) => update({ muted: e.target.checked ? "1" : "" })}
            />
            Show quarantined
          </label>
        </FilterBar>
      </form>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      <p className="muted">
        A quarantined test keeps running and showing up here and on its runs, but its failures stop counting:
        not in a run's verdict, not in failure alerts, and not in the collector's <code>--gate</code>.
      </p>
      <p role="status" className="muted">
        {undo && (
          <>
            {undo.muted ? "Quarantined" : "Released"} {undo.name}.{" "}
            <button
              type="button"
              onClick={() => {
                void change(undo.testKey, undo.muted);
                setUndo(null);
              }}
            >
              Undo
            </button>
          </>
        )}
      </p>
      {query.isPending && <p className="muted">Loading flaky tests…</p>}
      {query.data && rows.length === 0 && (
        <p className="muted">No flaky tests in the last {windowDays} days.</p>
      )}

      {rows.length > 0 && (
        <div className="card" tabIndex={0} role="region" aria-label="Flaky tests">
          <table className="data">
            <thead>
              <tr>
                <th>Test</th><th className="hide-narrow">Reason</th><th className="hide-narrow">Flips</th><SortableTh label="Flip rate" sortKey="rate" sort={sort} onSort={onSort} />
                <th className="hide-narrow">Runs</th><th>Last status</th>
                <SortableTh label="Last seen" sortKey="seen" sort={sort} onSort={onSort} className="hide-narrow" />
                <th className="hide-narrow">Commits</th>
                <th><span className="sr-only">Quarantine</span></th>
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
                      { label: "Reason", value: r.reason === "same_commit" ? "Confirmed" : "Suspected" },
                      { label: "Flips", value: r.flips ?? "—" },
                      { label: "Runs", value: r.runs },
                      { label: "Last seen", value: new Date(r.last_seen).toLocaleString() },
                      { label: "Commits", value: r.commits.length === 0 ? "—" : r.commits.map((c) => c.commit_sha.slice(0, 7)).join(", ") },
                    ]} />
                  </td>
                  <td className="hide-narrow">{r.reason === "same_commit" ? "Confirmed" : "Suspected"}</td>
                  <td className="hide-narrow">{r.flips ?? "—"}</td>
                  <td>{formatPassRate(r.flip_rate)}</td>
                  <td className="hide-narrow">{r.runs}</td>
                  <td><StatusDot status={r.last_status} /></td>
                  <td className="hide-narrow">{new Date(r.last_seen).toLocaleString()}</td>
                  <td className="hide-narrow">
                    {r.commits.length === 0 ? (
                      <span className="muted">—</span>
                    ) : (
                      <details>
                        <summary>{r.commits.length} commit(s)</summary>
                        <ul>
                          {r.commits.map((c, i) => (
                            <li key={i}>
                              {c.commit_sha.slice(0, 7)}
                              {c.environment && <span className="muted"> · {c.environment}</span>}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </td>
                  <td>
                    {r.muted && <span className="muted">In quarantine · </span>}
                    <ConfirmButton
                      label={r.muted ? "Release" : "Quarantine"}
                      ariaLabel={r.muted ? `Release ${r.name} from quarantine` : `Quarantine ${r.name}`}
                      question={
                        r.muted
                          ? `Released tests fail runs again. Release ${r.name}?`
                          : `Quarantined tests don't fail runs. Quarantine ${r.name}?`
                      }
                      confirmLabel={r.muted ? "Release" : "Quarantine"}
                      onConfirm={() => toggle(r.test_key, r.name, r.muted === true)}
                      disabled={pending.has(r.test_key)}
                    />
                    {failed.has(r.test_key) && (
                      <span role="alert" className="field-error">
                        Could not change {r.name}. Try again.
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
