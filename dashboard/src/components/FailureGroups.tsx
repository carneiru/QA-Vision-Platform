import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CauseHistory, getFailureGroups } from "../api/runs";
import ErrorBanner from "./ErrorBanner";
import StatusDot from "./StatusDot";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** How long a cause has been around on this branch, in words. */
export function historyText(h: CauseHistory): string {
  if (h.window === 1) return "First run on this branch";
  if (h.streak === 1 && h.seen_in === 1) return "New in this run";
  const streak = h.streak > 1 ? `In the last ${h.streak} runs, since #${h.since_run_id}` : "Back after a passing run";
  return h.seen_in > h.streak ? `${streak} · ${h.seen_in} of the last ${h.window} runs` : streak;
}

export const isNewCause = (h: CauseHistory) => h.window > 1 && h.streak === 1 && h.seen_in === 1;

/** A run's failures by cause, biggest first: one broken locator reads as one problem, not forty. */
export default function FailureGroups({ runId, projectId }: { runId: number; projectId: string | undefined }) {
  const query = useQuery({ queryKey: ["failure-groups", runId], queryFn: () => getFailureGroups(runId) });
  const data = query.data;

  return (
    <section className="card" aria-labelledby="causes">
      <h3 id="causes">Failures by cause</h3>
      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Grouping failures…</p>}
      {data && (
        <>
          <p className="muted">
            {plural(data.total, "failure")}, {plural(data.groups.length, "cause")}. Tests share a cause when their
            first error line matches once numbers, ids and hashes are ignored.
          </p>
          <ol className="cause-list">
            {data.groups.map((g) => (
              <li key={g.signature}>
                <div className="cause-head">
                  <span className="cause-count">{g.count}×</span>
                  {g.headline ? (
                    <code className="cause-line">{g.headline}</code>
                  ) : (
                    <span className="muted">No error message</span>
                  )}
                </div>
                <p className={isNewCause(g.history) ? "cause-history cause-new" : "cause-history"}>
                  {historyText(g.history)}
                  {(g.quarantined ?? 0) > 0 &&
                    (g.quarantined === g.count ? " · all in quarantine" : ` · ${g.quarantined} in quarantine`)}
                </p>
                <details>
                  <summary>
                    {plural(g.count, "test")}
                    {g.errored > 0 && g.failed > 0 && ` (${g.failed} failed, ${g.errored} errored)`}
                  </summary>
                  <ul className="cause-tests">
                    {g.tests.map((t) => (
                      <li key={t.id}>
                        <Link to={`/projects/${projectId}/tests/${encodeURIComponent(t.test_key)}`}>{t.name}</Link>
                        <span className="muted"> {t.suite} / {t.class_name} · </span>
                        <StatusDot status={t.status} />
                        {t.quarantined && <span className="muted"> · quarantined</span>}
                      </li>
                    ))}
                    {g.count > g.tests.length && <li className="muted">and {g.count - g.tests.length} more</li>}
                  </ul>
                </details>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
