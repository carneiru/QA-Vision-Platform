import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, CircleX } from "lucide-react";
import type { CaseQuery } from "../api/cases";
import { type FeatureRow, groupCasesQuery } from "../lib/featureQueries";
import CaseTable, { type CaseRowData, isRunnable } from "./CaseTable";
import ErrorBanner from "./ErrorBanner";
import NarrowMeta from "./NarrowMeta";

export const MANUAL_GROUP = "No feature (manual)";

/** A feature row's name: its Feature, else its file name; the manual group has its own label. */
export const featureLabel = (row: { feature_name: string | null; path: string | null }) =>
  row.path == null ? MANUAL_GROUP : row.feature_name || row.path.slice(row.path.lastIndexOf("/") + 1);

interface Props {
  projectId: number;
  rows: FeatureRow[];
  selectable: boolean;
  picked: Map<number, string>;
  onToggle: (c: CaseRowData) => void;
  onToggleAll: (on: boolean, rows: CaseRowData[]) => void;
  /** The filters in force, for the manual group's cases. */
  filters: Omit<CaseQuery, "limit" | "offset">;
  /** Case numbers whose latest result failed, or null when unknown (the row then shows no count). */
  failing: Set<number> | null;
  /** Called with the number of expanded rows, so the page can show the run legend. */
  onExpandedChange?: (count: number) => void;
}

/** The Feature view of the Cases list: one row per .feature file, expanding in place to its scenarios. */
export default function FeatureList({ projectId, rows, selectable, picked, onToggle, onToggleAll, filters, failing, onExpandedChange }: Props) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const qc = useQueryClient();
  const idOf = (row: FeatureRow) => row.path ?? "\0manual";
  const columns = (selectable ? 1 : 0) + 3;

  function flip(row: FeatureRow) {
    const next = new Set(open);
    if (!next.delete(idOf(row))) next.add(idOf(row));
    setOpen(next);
    onExpandedChange?.(next.size);
  }

  // Checking a feature selects every runnable scenario it holds; the titles come with its cases
  async function pickRow(row: FeatureRow, on: boolean) {
    const cases = await qc.fetchQuery(groupCasesQuery(projectId, row, filters));
    onToggleAll(on, cases.filter(isRunnable));
  }

  return (
    <table className="data feature-list">
      <thead>
        <tr>
          {selectable && <th className="select-col"><span className="sr-only">Select</span></th>}
          <th>Feature</th><th className="num">Scenarios</th><th className="hide-narrow">Latest result</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const label = featureLabel(row);
          const expanded = open.has(idOf(row));
          const shown = row.case_numbers.filter((n) => picked.has(n)).length;
          const failed = failing && row.path != null ? row.case_numbers.filter((n) => failing.has(n)).length : 0;
          return [
            <tr key={idOf(row)} className="feature-row">
              {selectable && (
                <td className="select-col">
                  {row.path != null && (
                    <input type="checkbox" aria-label={`Select every scenario of ${label}`}
                      checked={shown > 0 && shown === row.case_numbers.length}
                      ref={(el) => { if (el) el.indeterminate = shown > 0 && shown < row.case_numbers.length; }}
                      onChange={(e) => void pickRow(row, e.target.checked)} />
                  )}
                </td>
              )}
              <td className="wrap-anywhere">
                <div className="feature-head">
                  <button type="button" className="disclosure" aria-expanded={expanded} aria-label={`Show scenarios of ${label}`}
                    onClick={() => flip(row)}>
                    <ChevronRight size={16} aria-hidden="true" />
                  </button>
                  <span className="feature-text">
                    {row.path != null ? (
                      <Link className="feature-name" to={`/projects/${projectId}/cases/feature?path=${encodeURIComponent(row.path)}`}>{label}</Link>
                    ) : (
                      <span className="feature-name">{label}</span>
                    )}
                    {row.folder ? <span className="feature-folder">{row.folder}</span> : null}
                    <NarrowMeta items={[{ label: "Latest result", value: failed > 0 ? `${failed} failing` : null }]} />
                  </span>
                </div>
              </td>
              <td className="num">{row.case_count === 1 ? "1 scenario" : `${row.case_count} scenarios`}</td>
              <td className="hide-narrow">
                {failed > 0 && <span className="failing-count"><CircleX size={14} aria-hidden="true" /> {failed} failing</span>}
              </td>
            </tr>,
            expanded && (
              <tr key={`${idOf(row)}-cases`} className="feature-cases">
                <td colSpan={columns}>
                  <GroupCases projectId={projectId} row={row} label={`Scenarios of ${label}`} selectable={selectable}
                    picked={picked} onToggle={onToggle} filters={filters} />
                </td>
              </tr>
            ),
          ];
        })}
      </tbody>
    </table>
  );
}

function GroupCases({ projectId, row, label, selectable, picked, onToggle, filters }: {
  projectId: number; row: FeatureRow; label: string; selectable: boolean; picked: Map<number, string>;
  onToggle: (c: CaseRowData) => void; filters: Omit<CaseQuery, "limit" | "offset">;
}) {
  const cases = useQuery(groupCasesQuery(projectId, row, filters));
  if (cases.error != null) return <ErrorBanner error={cases.error} onRetry={() => cases.refetch()} />;
  if (!cases.data) return <p className="muted">Loading scenarios…</p>;
  return (
    <>
      <CaseTable projectId={projectId} cases={cases.data} selectable={selectable} picked={picked} onToggle={onToggle} label={label} />
      {row.case_count > cases.data.length && (
        <p className="muted feature-more">
          {`Showing ${cases.data.length} of ${row.case_count}. `}
          <Link to={`/projects/${projectId}/cases?group=scenario${row.path == null ? "&origin=manual" : `&feature=${encodeURIComponent(row.feature_name ?? "")}`}`}>
            See them all in Scenario view
          </Link>
        </p>
      )}
      {cases.data.length === 0 && <p className="muted">No scenarios match the filters.</p>}
    </>
  );
}
