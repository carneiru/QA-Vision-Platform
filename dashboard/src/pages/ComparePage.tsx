import { FormEvent, useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CompareItem, RunOverview, compareRuns } from "../api/runs";
import { formatDuration } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import NarrowMeta from "../components/NarrowMeta";
import StatusDot from "../components/StatusDot";

const MAX_LISTED = 200;

const SECTIONS = [
  { key: "new_failures", title: "New failures", hint: "Passed in the base run, fail now." },
  { key: "fixed", title: "Fixed", hint: "Failed in the base run, pass now." },
  { key: "still_failing", title: "Still failing", hint: "Failing in both runs." },
  { key: "slower", title: "Slower", hint: "Passed in both, at least 1 s and 50% slower now." },
  { key: "added", title: "Added", hint: "Only in this run." },
  { key: "removed", title: "Removed", hint: "Only in the base run." },
] as const;

type SectionKey = (typeof SECTIONS)[number]["key"];

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function RunLine({ label, run }: { label: string; run: RunOverview }) {
  return (
    <p className="muted compare-run">
      <strong>{label}</strong> <Link to={`../${run.id}`} relative="path">#{run.id}</Link> ·{" "}
      {new Date(run.started_at).toLocaleString()} · {run.branch ?? "no branch"} ·{" "}
      {run.commit_sha ? <code>{run.commit_sha.slice(0, 7)}</code> : "no commit"} · {run.passed} passed,{" "}
      {run.failed + run.errored} failing
    </p>
  );
}

function Status({ value }: { value: string | null }) {
  return value ? <StatusDot status={value} /> : <span className="muted">—</span>;
}

function Section({ projectId, kind, items, total }: {
  projectId: string | undefined;
  kind: (typeof SECTIONS)[number];
  items: CompareItem[];
  total: number;
}) {
  const slower = kind.key === "slower";
  return (
    <section className="card" aria-labelledby={`cmp-${kind.key}`} role="region">
      <h3 id={`cmp-${kind.key}`}>{kind.title} <span className="muted">({total})</span></h3>
      <p className="muted">{kind.hint}{total > items.length && ` Showing the first ${MAX_LISTED}.`}</p>
      <table className="data">
        <thead>
          <tr>
            <th>Test</th>
            <th>Before</th>
            <th>Now</th>
            <th className={slower ? undefined : "hide-narrow"}>{slower ? "Change" : "Message"}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((t) => (
            <tr key={t.test_key}>
              <td className="wrap-anywhere">
                <Link to={`/projects/${projectId}/tests/${encodeURIComponent(t.test_key)}`}>{t.name}</Link>
                <div className="muted">{t.suite} / {t.class_name}</div>
                {!slower && <NarrowMeta items={[{ label: "Message", value: t.message ?? "—" }]} />}
              </td>
              {slower ? (
                <>
                  <td>{formatDuration(t.base_duration_ms ?? 0)}</td>
                  <td>{formatDuration(t.head_duration_ms ?? 0)}</td>
                  <td>+{formatDuration((t.head_duration_ms ?? 0) - (t.base_duration_ms ?? 0))}</td>
                </>
              ) : (
                <>
                  <td><Status value={t.base_status} /></td>
                  <td><Status value={t.head_status} /></td>
                  <td className="hide-narrow wrap-anywhere">{t.message ? <code>{t.message}</code> : <span className="muted">—</span>}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** One run against another, test by test: what broke, what got fixed, what got slower. */
export default function ComparePage() {
  const { projectId, runId, baseId } = useParams();
  const head = Number(runId);
  const base = Number(baseId);
  const navigate = useNavigate();
  const [other, setOther] = useState(String(base));
  useEffect(() => setOther(String(base)), [base]);

  const query = useQuery({ queryKey: ["compare", head, base], queryFn: () => compareRuns(head, base) });
  const data = query.data;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const next = Number(other);
    if (Number.isInteger(next) && next > 0) navigate(`/projects/${projectId}/runs/${head}/compare/${next}`);
  }

  const c = data?.counts;
  return (
    <section>
      <p>
        <Link className="link-arrow" to={`/projects/${projectId}/runs/${head}`}><ArrowLeft size={14} aria-hidden="true" /> Run #{head}</Link>
      </p>
      <h2>Run #{head} compared with #{base}</h2>

      <form className="filters" onSubmit={onSubmit}>
        <label>
          Compare with run #
          <input type="number" min={1} inputMode="numeric" required value={other} onChange={(e) => setOther(e.target.value)} />
        </label>
        <button type="submit">Compare</button>
      </form>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Comparing…</p>}
      {data && c && (
        <>
          <RunLine label="Base" run={data.base} />
          <RunLine label="Now" run={data.head} />
          <p className="compare-summary">
            {plural(c.new_failures, "new failure", "new failures")} · {c.fixed} fixed · {c.still_failing} still failing ·{" "}
            {c.slower} slower · {c.added} added · {c.removed} removed · {c.unchanged} unchanged
          </p>
          {SECTIONS.filter((s) => c[s.key as SectionKey] > 0).map((s) => (
            <Section key={s.key} projectId={projectId} kind={s} items={data[s.key as SectionKey]} total={c[s.key as SectionKey]} />
          ))}
          {SECTIONS.every((s) => c[s.key as SectionKey] === 0) && (
            <p className="muted">No test changed outcome or got notably slower.</p>
          )}
        </>
      )}
    </section>
  );
}
