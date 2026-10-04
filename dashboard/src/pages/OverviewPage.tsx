import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, GitBranch, GitCommitHorizontal, Server, XCircle } from "lucide-react";
import { formatDuration, formatPassRate, getFlaky, getTrends } from "../api/analytics";
import { getRun, listRuns, Run, RunResult } from "../api/runs";
import ErrorBanner from "../components/ErrorBanner";
import StatusDot from "../components/StatusDot";

const MAX_FAILURES = 8;
// The Flaky view's defaults, so both screens count the same tests
const FLAKY = { windowDays: 14, minRuns: 5, minFlipRate: 0.3 };

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
function ago(iso: string): string {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const steps: [number, Intl.RelativeTimeFormatUnit][] = [[60, "second"], [60, "minute"], [24, "hour"], [30, "day"], [12, "month"]];
  let value = seconds;
  for (const [size, unit] of steps) {
    if (Math.abs(value) < size) return relative.format(Math.round(value), unit);
    value /= size;
  }
  return relative.format(Math.round(value), "year");
}

const firstLine = (text: string | null) => (text ?? "").split("\n")[0];

/** "What is broken now" in one screen: the latest run's verdict and failures,
 *  then the week's pass rate and the flaky count, each one click from depth. */
export default function OverviewPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

  const runs = useQuery({ queryKey: ["runs", id, "latest"], queryFn: () => listRuns(id, { limit: 1, offset: 0 }) });
  const latest: Run | undefined = runs.data?.[0];
  const failed = useQuery({
    queryKey: ["run", latest?.id, "failed"],
    queryFn: () => getRun(latest!.id, "failed"),
    enabled: latest !== undefined && latest.failed > 0,
  });
  const errored = useQuery({
    queryKey: ["run", latest?.id, "errored"],
    queryFn: () => getRun(latest!.id, "errored"),
    enabled: latest !== undefined && latest.errored > 0,
  });
  const weeks = useQuery({
    queryKey: ["trends", id, "overview-weeks", tz],
    queryFn: () => getTrends(id, { days: 14, tz, bucket: "week" }),
    enabled: latest !== undefined,
  });
  const flaky = useQuery({
    queryKey: ["flaky", id, "overview"],
    queryFn: () => getFlaky(id, FLAKY),
    enabled: latest !== undefined,
  });

  if (runs.error != null) return <ErrorBanner error={runs.error} onRetry={() => runs.refetch()} />;
  if (runs.isPending) return <p className="muted">Loading overview…</p>;

  if (!latest) {
    return (
      <div className="card">
        <h2>No runs yet</h2>
        <p className="muted">
          Results appear here after the first upload from CI. Create an API key, paste the CI
          snippet into your pipeline, and the next build reports its tests.
        </p>
        <Link to={`/projects/${id}/settings`}>Set up an API key and CI →</Link>
      </div>
    );
  }

  const broken = latest.failed + latest.errored;
  const failures: RunResult[] = [...(failed.data?.results ?? []), ...(errored.data?.results ?? [])];
  const buckets = weeks.data?.days ?? [];
  const thisWeek = buckets[buckets.length - 1];
  const lastWeek = buckets.length > 1 ? buckets[buckets.length - 2] : undefined;
  const confirmed = flaky.data?.filter((r) => r.reason === "same_commit").length ?? 0;
  const suspected = flaky.data?.filter((r) => r.reason === "flips").length ?? 0;

  return (
    <div className="overview-grid">
      <section className="card wide" aria-labelledby="latest-run">
        <div className="card-head">
          <h2 id="latest-run">Latest run</h2>
          {broken > 0 ? (
            <span className="badge badge-failed"><XCircle size={14} aria-hidden="true" /> Failed</span>
          ) : (
            <span className="badge badge-passed"><CheckCircle2 size={14} aria-hidden="true" /> Passed</span>
          )}
        </div>
        {latest.commit_message && <p>{latest.commit_message}</p>}
        <div className="meta">
          {latest.branch && <span><GitBranch size={14} aria-hidden="true" /> {latest.branch}</span>}
          {latest.commit_sha && <span><GitCommitHorizontal size={14} aria-hidden="true" /> <code>{latest.commit_sha.slice(0, 7)}</code></span>}
          {latest.environment && <span><Server size={14} aria-hidden="true" /> {latest.environment}</span>}
          <span><Clock size={14} aria-hidden="true" /> {ago(latest.started_at)} · {formatDuration(latest.duration_ms)}</span>
        </div>
        <div className="meta">
          <span><StatusDot status="passed" label={`${latest.passed} passed`} /></span>
          <span><StatusDot status="failed" label={`${latest.failed} failed`} /></span>
          <span><StatusDot status="errored" label={`${latest.errored} errored`} /></span>
          <span><StatusDot status="skipped" label={`${latest.skipped} skipped`} /></span>
        </div>
        <div className="card-foot">
          <Link to={`/projects/${id}/runs/${latest.id}`}>Open run #{latest.id} →</Link>
        </div>
      </section>

      <section className="card" aria-labelledby="failing">
        <h2 id="failing">Failing in this run</h2>
        {broken === 0 && <p className="muted">Nothing failed in the latest run.</p>}
        {broken > 0 && failures.length === 0 && <p className="muted">Loading failures…</p>}
        {failures.length > 0 && (
          <ul className="fail-list">
            {failures.slice(0, MAX_FAILURES).map((r) => (
              <li key={`${r.status}-${r.id}`}>
                <Link to={`/projects/${id}/tests/${encodeURIComponent(r.test_key)}`}>{r.name}</Link>
                <span className="where">{r.suite} / {r.class_name}</span>
                {r.message && <span className="msg">{firstLine(r.message)}</span>}
              </li>
            ))}
          </ul>
        )}
        {broken > MAX_FAILURES && (
          <div className="card-foot">
            <Link to={`/projects/${id}/runs/${latest.id}`}>All {broken} failures →</Link>
          </div>
        )}
      </section>

      <section className="card" aria-labelledby="pass-rate">
        <h2 id="pass-rate">Pass rate this week</h2>
        {weeks.isPending && <p className="muted">Loading…</p>}
        {thisWeek && (
          <>
            <div className="stat-big">{formatPassRate(thisWeek.pass_rate)}</div>
            <p className="muted">
              {thisWeek.runs} {thisWeek.runs === 1 ? "run" : "runs"} this week
              {" · "}
              {lastWeek && lastWeek.pass_rate !== null
                ? `${formatPassRate(lastWeek.pass_rate)} the week before`
                : "no runs the week before"}
            </p>
          </>
        )}
        <div className="card-foot">
          <Link to={`/projects/${id}/trends`}>Trends →</Link>
        </div>
      </section>

      <section className="card" aria-labelledby="flaky-count">
        <h2 id="flaky-count">Flaky tests, last 14 days</h2>
        {flaky.isPending && <p className="muted">Loading…</p>}
        {flaky.data && (
          <>
            <div className="stat-big">{confirmed + suspected}</div>
            <p className="muted">{confirmed} confirmed · {suspected} suspected</p>
          </>
        )}
        <div className="card-foot">
          <Link to={`/projects/${id}/flaky`}>Flaky tests →</Link>
        </div>
      </section>
    </div>
  );
}
