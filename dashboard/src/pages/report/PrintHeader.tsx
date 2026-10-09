import type { AppliedFilter } from "../../components/FilterChips";
import { formatPeriod } from "./describeFilters";
import { type ReportFilters, addDays } from "./useReportFilters";

/** Printed under the title only (spec: Print / Save as PDF): the period and zone, every filter, the period the
 *  deltas compare with, and when the report was generated. */
export default function PrintHeader({ filters, tz, applied, generatedAt }: {
  filters: ReportFilters;
  tz: string;
  applied: AppliedFilter[];
  generatedAt: string | null;
}) {
  const previousFrom = addDays(filters.from, -filters.days);
  const previousTo = addDays(filters.from, -1);
  return (
    <div className="print-only report-print-header">
      <p><strong>Period:</strong> {formatPeriod(filters.from, filters.to)} ({filters.days} days), {tz}</p>
      <p><strong>Compared with:</strong> {formatPeriod(previousFrom, previousTo)}</p>
      {applied.length === 0
        ? <p><strong>Filters:</strong> none</p>
        : <ul>{applied.map((f) => <li key={f.key}>{f.name}: {f.value}</li>)}</ul>}
      <p><strong>Generated:</strong> {new Date(generatedAt ?? Date.now()).toLocaleString()}</p>
    </div>
  );
}
