import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Printer, RefreshCw, X } from "lucide-react";
import { getProject } from "../../api/orgs";
import { ChartPatternDefs } from "../../components/ChartKit";
import PageHeader from "../../components/PageHeader";
import PrintHeader from "./PrintHeader";
import ReportFilterBar from "./ReportFilterBar";
import { describeFilters, formatPeriod } from "./describeFilters";
import FlakySection from "./sections/FlakySection";
import SummarySection from "./sections/SummarySection";
import { todayIn, useReportFilters } from "./useReportFilters";
import { useReportRequest, useReportSection } from "./useReportRequest";

/** "Report updated", once, when every section asked after a filter change has settled (spec: Filter bar). The first
 *  load is not announced. */
export function useAnnouncement(signature: string | null, busy: boolean): string {
  const [message, setMessage] = useState("");
  const last = useRef<string | null>(null);
  const waiting = useRef(false);
  useEffect(() => {
    if (signature === null) return;
    if (last.current !== null && last.current !== signature) {
      waiting.current = true;
      setMessage("");
    }
    last.current = signature;
  }, [signature]);
  useEffect(() => {
    if (waiting.current && !busy) {
      waiting.current = false;
      setMessage("Report updated");
    }
  }, [busy, signature]);
  return message;
}

/** Keeps every chart's data table open on paper (spec: Print / Save as PDF). */
function usePrintOpensDataTables() {
  useEffect(() => {
    const opened: HTMLDetailsElement[] = [];
    const before = () => {
      document.querySelectorAll<HTMLDetailsElement>(".report details.chart-data:not([open])").forEach((d) => {
        d.open = true;
        opened.push(d);
      });
    };
    const after = () => opened.splice(0).forEach((d) => { d.open = false; });
    window.addEventListener("beforeprint", before);
    window.addEventListener("afterprint", after);
    return () => {
      window.removeEventListener("beforeprint", before);
      window.removeEventListener("afterprint", after);
    };
  }, []);
}

export default function ReportPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const today = todayIn(tz);
  const qc = useQueryClient();
  const { filters, update, clearAll, notice, dismissNotice } = useReportFilters(tz);
  const [formOpened, setFormOpened] = useState(false);
  const project = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id) });
  const { gate, caseAreas, runUrls, defaultBranch, effectiveBranch } = useReportRequest(id, filters, tz, { loadCaseAreas: formOpened });
  const summary = useReportSection(id, gate, "summary");
  usePrintOpensDataTables();

  const busy = summary.fetchStatus === "fetching";
  const announcement = useAnnouncement(gate.state === "ready" ? JSON.stringify(gate.key) : null, busy);
  const applied = describeFilters(filters, defaultBranch, caseAreas.data);
  const generated = summary.data?.generated_at ?? null;
  const subtitle = `${project.data?.name ?? "Project"}: quality report. ${formatPeriod(filters.from, filters.to)} (${filters.days} days), ${tz}.`
    + (generated ? ` Generated ${new Date(generated).toLocaleString()}.` : "")
    + (applied.length ? ` ${applied.map((f) => `${f.name}: ${f.value}`).join("; ")}.` : "");

  function refresh() {
    for (const key of [["report", id], ["report-flaky", id], ["case-areas", id], ["run-urls", id]]) {
      void qc.invalidateQueries({ queryKey: key });
    }
  }

  return (
    <div className="report">
      <ChartPatternDefs />
      <PageHeader
        title="Report"
        subtitle={subtitle}
        actions={
          <div className="report-actions no-print">
            <button type="button" onClick={refresh}><RefreshCw size={15} aria-hidden="true" /> Refresh</button>
            <button type="button" onClick={() => window.print()}><Printer size={15} aria-hidden="true" /> Save as PDF</button>
          </div>
        }
      />
      <PrintHeader filters={filters} tz={tz} applied={applied} generatedAt={generated} />
      {notice && (
        <div className="report-notice no-print" role="status">
          <span>Some filters in the link were not valid and were removed</span>
          <button type="button" className="ghost" aria-label="Dismiss the notice" onClick={dismissNotice}><X size={14} aria-hidden="true" /></button>
        </div>
      )}
      <ReportFilterBar
        filters={filters} update={update} clearAll={clearAll} today={today} defaultBranch={defaultBranch}
        caseAreas={{ data: caseAreas.data, error: caseAreas.error, isPending: caseAreas.isFetching, refetch: caseAreas.refetch }}
        runUrls={{ error: runUrls.error, refetch: runUrls.refetch }}
        facets={summary.data?.summary?.facets}
        onFormOpen={() => setFormOpened(true)}
      />
      <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
      <SummarySection projectId={id} gate={gate} query={summary} branch={effectiveBranch} environment={filters.environment}
        onClearFilters={clearAll} onTry={update} />
      <FlakySection projectId={id} gate={gate} filters={filters} branch={effectiveBranch} today={today} />
    </div>
  );
}
