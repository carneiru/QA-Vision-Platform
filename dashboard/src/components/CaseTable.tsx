import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Bot, FileCode } from "lucide-react";
import type { CaseStatus, Priority } from "../api/cases";
import { getRunStrip } from "../api/analytics";
import { MAX_RUN_CASES } from "../api/runRequests";
import NarrowMeta from "./NarrowMeta";
import RunStrip, { RunStripSkeleton } from "./RunStrip";
import { CaseStatusPill } from "./StatusPill";

/** What a case row shows: a full Case from /cases, or a feature file's case from /features/detail. */
export interface CaseRowData {
  number: number;
  key: string;
  title: string;
  status: CaseStatus;
  priority: Priority;
  automated_test_key: string | null;
  source_path: string | null;
  labels?: string[];
}

/** Only an imported, active case can run: the workflow runs a scenario of a .feature file. */
export const isRunnable = (c: { source_path: string | null; status: CaseStatus }) => c.source_path != null && c.status !== "archived";

export function Labels({ labels }: { labels: string[] }) {
  if (labels.length === 0) return null;
  return (
    <ul className="chip-list" aria-label="Labels">
      {labels.map((l) => <li key={l} className="chip">{l}</li>)}
    </ul>
  );
}

/** Last runs for a set of linked cases: one strip request per set, shared by every reader of the same keys. */
export function useRunStrips(projectId: number, testKeys: (string | null)[]) {
  const keys = useMemo(() => [...new Set(testKeys.filter((k): k is string => !!k))].sort(), [testKeys]);
  const strip = useQuery({
    queryKey: ["run-strip", projectId, keys],
    queryFn: () => getRunStrip(projectId, keys),
    enabled: keys.length > 0,
    staleTime: 60_000,
  });
  // Shown in its own column on wide screens and in the narrow line under the title on phones
  const lastRuns = (key: string | null) =>
    !key ? (
      <span className="muted">not linked</span>
    ) : strip.isError ? (
      <span aria-label="Last runs unavailable">—</span>
    ) : strip.data ? (
      <RunStrip projectId={projectId} runs={strip.data.runs} statuses={strip.data.statuses[key.toLowerCase()] ?? strip.data.runs.map(() => null)} />
    ) : (
      <RunStripSkeleton />
    );
  // Phones get a count instead of the strip: the same information, in a line, without a second set of links
  const lastRunsSummary = (key: string | null): string | null => {
    if (!key || !strip.data) return null;
    const ran = (strip.data.statuses[key.toLowerCase()] ?? []).filter((s) => s !== null);
    if (ran.length === 0) return "none yet";
    const count = (status: string) => ran.filter((s) => s === status).length;
    const parts = (["failed", "rerun", "passed", "skipped"] as const).filter((st) => count(st) > 0).map((st) => `${count(st)} ${st}`);
    return `${parts.join(", ")} of the last ${ran.length}`;
  };
  return { keys, lastRuns, lastRunsSummary };
}

interface Props {
  projectId: number;
  cases: CaseRowData[];
  /** Editors get the selection column. */
  selectable: boolean;
  picked: Map<number, string>;
  onToggle: (c: CaseRowData) => void;
  /** The header's select-all box; left out where a parent row already selects the set (a feature row). */
  onToggleAll?: (on: boolean, rows: CaseRowData[]) => void;
  /** Accessible name of the table, when it is one of several (a feature's scenarios). */
  label?: string;
}

/** The Scenario rows of the Cases list: checkbox, title link, last runs, priority, status, automated. */
export default function CaseTable({ projectId, cases, selectable, picked, onToggle, onToggleAll, label }: Props) {
  const { lastRuns, lastRunsSummary } = useRunStrips(projectId, useMemo(() => cases.map((c) => c.automated_test_key), [cases]));
  const runnable = cases.filter(isRunnable);
  return (
    <table className="data" aria-label={label}>
      <thead>
        <tr>
          {selectable && (
            <th className="select-col">
              {onToggleAll ? (
                <input type="checkbox" aria-label="Select all imported cases on this page" disabled={runnable.length === 0}
                  checked={runnable.length > 0 && runnable.every((c) => picked.has(c.number))}
                  ref={(el) => { if (el) el.indeterminate = runnable.some((c) => picked.has(c.number)) && !runnable.every((c) => picked.has(c.number)); }}
                  onChange={(e) => onToggleAll(e.target.checked, runnable)} />
              ) : <span className="sr-only">Select</span>}
            </th>
          )}
          <th>Title</th><th className="hide-narrow">Last runs</th><th className="hide-narrow">Priority</th><th>Status</th>
          <th className="hide-narrow">Automated</th>
        </tr>
      </thead>
      <tbody>
        {cases.map((c) => (
          <tr key={c.number}>
            {selectable && (
              <td className="select-col">
                {isRunnable(c) && (
                  <input type="checkbox" aria-label={`Select ${c.key} ${c.title}`} checked={picked.has(c.number)}
                    disabled={!picked.has(c.number) && picked.size >= MAX_RUN_CASES} onChange={() => onToggle(c)}
                    onFocus={(e) => e.currentTarget.scrollIntoView?.({ block: "nearest" })} />
                )}
              </td>
            )}
            <td className="wrap-anywhere">
              {c.source_path && <FileCode size={14} aria-label="Imported" role="img" />}{c.source_path && " "}
              <Link className="case-title" to={`/projects/${projectId}/cases/${c.number}`}>{c.title}</Link>
              <Labels labels={c.labels ?? []} />
              <NarrowMeta items={[
                { label: "Last runs", value: lastRunsSummary(c.automated_test_key) },
                { label: "Priority", value: c.priority },
                { label: "Automated", value: c.automated_test_key ? "Linked" : "Manual" },
              ]} />
            </td>
            <td className="hide-narrow">{lastRuns(c.automated_test_key)}</td>
            <td className="hide-narrow">{c.priority}</td>
            <td><CaseStatusPill status={c.status} /></td>
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
  );
}
