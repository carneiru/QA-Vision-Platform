import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getFailureGroups } from "../api/runs";
import ErrorBanner from "./ErrorBanner";
import StatusDot from "./StatusDot";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

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
