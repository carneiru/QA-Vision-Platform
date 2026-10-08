import { type ReactNode, useMemo, useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Info } from "lucide-react";
import { type Case, type FeatureCase, type FeatureDetail, listCases } from "../api/cases";
import { MAX_RUN_CASES } from "../api/runRequests";
import { useRunStrips } from "../components/CaseTable";
import ErrorBanner from "../components/ErrorBanner";
import { featureLabel } from "../components/FeatureList";
import GherkinBlock from "../components/GherkinBlock";
import PageHeader from "../components/PageHeader";
import RunControl from "../components/RunControl";
import { GROUP_CASES_MAX, featureDetailQuery, fileLabel } from "../lib/featureQueries";
import { useCanEdit } from "../lib/useCanEdit";

const HEADING = /^\s*[^\s:#@|][^:#@|]*:/;

/** The file as the cases hold it, for a file imported before raw files were stored: the Feature line, then
 *  each scenario's own Gherkin (or its title), with the line its heading lands on. */
export function rebuildFeature(detail: FeatureDetail, cases: Case[]): { text: string; lines: Map<number, number> } {
  const byNumber = new Map(cases.map((c) => [c.number, c]));
  const out = [`Feature: ${detail.feature_name ?? featureLabel(detail)}`];
  const lines = new Map<number, number>();
  for (const fc of detail.cases) {
    out.push("");
    const block = (byNumber.get(fc.number)?.gherkin ?? `Scenario: ${fc.title}`).replace(/\s+$/, "").split("\n");
    const heading = block.findIndex((l) => HEADING.test(l));
    lines.set(fc.number, out.length + 1 + Math.max(heading, 0));
    out.push(...block);
  }
  return { text: out.join("\n"), lines };
}

/** One .feature file: its raw text with each scenario linked to its case, and Run feature. */
export default function FeaturePage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const canEdit = useCanEdit(id);
  const [params] = useSearchParams();
  const path = params.get("path") ?? "";
  const headingRef = useRef<HTMLHeadingElement>(null);
  const detail = useQuery({ ...featureDetailQuery(id, path), enabled: path !== "" });
  const data = detail.data;
  // Not stored yet: the scenarios are rebuilt from the cases' own Gherkin
  const rebuilt = useQuery({
    queryKey: ["feature-rebuild", id, path],
    enabled: data != null && data.content == null,
    queryFn: async () => {
      const page = await listCases(id, {
        feature: data!.feature_name ?? undefined, folder: data!.folder || undefined, origin: "imported", limit: GROUP_CASES_MAX, offset: 0,
      });
      return page.items.filter((c) => c.source_path === path);
    },
  });
  const source = useMemo(() => {
    if (!data) return null;
    if (data.content != null) {
      return { text: data.content, lines: new Map(data.cases.flatMap((c) => (c.line != null ? [[c.number, c.line] as const] : []))) };
    }
    return rebuilt.data ? rebuildFeature(data, rebuilt.data) : null;
  }, [data, rebuilt.data]);
  const cases = useMemo(() => data?.cases ?? [], [data]);
  const { lastRuns } = useRunStrips(id, useMemo(() => cases.map((c) => c.automated_test_key), [cases]));

  const chip = (c: FeatureCase) => (
    <>
      <Link className="case-chip" to={`/projects/${id}/cases/${c.number}`} title={c.title}>{c.key}</Link>
      {lastRuns(c.automated_test_key)}
    </>
  );
  const annotations = new Map<number, ReactNode>();
  const placed = new Set<number>();
  for (const c of cases) {
    const line = source?.lines.get(c.number);
    if (line != null && !annotations.has(line)) {
      annotations.set(line, chip(c));
      placed.add(c.number);
    }
  }
  const unplaced = source ? cases.filter((c) => !placed.has(c.number)) : [];
  const title = data ? featureLabel(data) : fileLabel(path) || "Feature";

  return (
    <section>
      <PageHeader
        title={title}
        subtitle={<code>{path}</code>}
        headingRef={headingRef}
        actions={canEdit && data ? (
          <RunControl projectId={id} label="Run feature"
            cases={cases.slice(0, MAX_RUN_CASES).map((c) => ({ number: c.number, title: c.title, testKey: c.automated_test_key }))}
            selection={{ case_numbers: cases.slice(0, MAX_RUN_CASES).map((c) => c.number) }}
            emptyReason="This feature has no scenarios" />
        ) : undefined}
      />
      {path === "" && <p className="muted">No feature file was named.</p>}
      {detail.error != null && <ErrorBanner error={detail.error} onRetry={() => detail.refetch()} />}
      {rebuilt.error != null && <ErrorBanner error={rebuilt.error} onRetry={() => rebuilt.refetch()} />}
      {(detail.isLoading || rebuilt.isLoading) && <p className="muted">Loading the feature…</p>}
      {data && data.content == null && (
        <p className="note" role="note">
          <Info size={16} aria-hidden="true" />
          <span>Re-import this file to see it exactly as written.</span>
        </p>
      )}
      {source && (
        <div className="card feature-source">
          <GherkinBlock text={source.text} label="Feature file" numbered annotations={annotations} />
        </div>
      )}
      {unplaced.length > 0 && (
        <div className="card">
          <h2>Scenarios not found in the file</h2>
          <ul className="ordered-cases">
            {unplaced.map((c) => (
              <li key={c.number}>
                <span className="muted">{c.key}</span>
                <Link className="case-title" to={`/projects/${id}/cases/${c.number}`}>{c.title}</Link>
                {lastRuns(c.automated_test_key)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
