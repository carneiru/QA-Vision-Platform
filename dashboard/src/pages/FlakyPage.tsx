import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatPassRate, getFlaky, muteFlaky, unmuteFlaky } from "../api/analytics";
import { downloadCsv, toCsv } from "../lib/csv";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import StatusDot from "../components/StatusDot";

export default function FlakyPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [windowDays, setWindowDays] = useState(14);
  // Drafts apply on submit, clamped to the API's bounds (min_runs ge=2,
  // min_flip_rate 0..1) so a cleared field never sends an invalid value.
  const [minRunsInput, setMinRunsInput] = useState("5");
  const [minFlipRateInput, setMinFlipRateInput] = useState("0.3");
  const [branchInput, setBranchInput] = useState("");
  const [minRuns, setMinRuns] = useState(5);
  const [minFlipRate, setMinFlipRate] = useState(0.3);
  const [branch, setBranch] = useState("");

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    const runs = Math.min(1000, Math.max(2, Math.round(Number(minRunsInput) || 0)));
    const rate = Math.min(1, Math.max(0, Number(minFlipRateInput) || 0));
    setMinRuns(runs);
    setMinFlipRate(rate);
    setBranch(branchInput.trim());
    setMinRunsInput(String(runs));
    setMinFlipRateInput(String(rate));
  }

  const [showMuted, setShowMuted] = useState(false);
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

  const muteToggle = useMutation({
    mutationFn: ({ testKey, muted }: { testKey: string; muted: boolean }) =>
      muted ? unmuteFlaky(id, testKey) : muteFlaky(id, testKey),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["flaky", id] }),
  });

  const rows = query.data ?? [];

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
            <select value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))}>
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
          <label style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <input
              type="checkbox"
              checked={showMuted}
              onChange={(e) => setShowMuted(e.target.checked)}
            />
            Show muted
          </label>
        </FilterBar>
      </form>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading flaky tests…</p>}
      {query.data && rows.length === 0 && (
        <p className="muted">No flaky tests in the last {windowDays} days.</p>
      )}

      {rows.length > 0 && (
        <div className="card" tabIndex={0} role="region" aria-label="Flaky tests">
          <table className="data">
            <thead>
              <tr>
                <th>Test</th><th className="hide-narrow">Reason</th><th className="hide-narrow">Flips</th><th>Flip rate</th>
                <th className="hide-narrow">Runs</th><th>Last status</th><th className="hide-narrow">Commits</th>
                <th><span className="sr-only">Mute</span></th>
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
                  </td>
                  <td className="hide-narrow">{r.reason === "same_commit" ? "Confirmed" : "Suspected"}</td>
                  <td className="hide-narrow">{r.flips ?? "—"}</td>
                  <td>{formatPassRate(r.flip_rate)}</td>
                  <td className="hide-narrow">{r.runs}</td>
                  <td><StatusDot status={r.last_status} /></td>
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
                    {r.muted && <span className="muted">Muted · </span>}
                    <button
                      onClick={() => muteToggle.mutate({ testKey: r.test_key, muted: r.muted === true })}
                      disabled={muteToggle.isPending}
                    >
                      {r.muted ? "Unmute" : "Mute"}
                    </button>
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
