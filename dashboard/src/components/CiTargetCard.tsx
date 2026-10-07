import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert } from "lucide-react";
import { CiTarget, deleteCiTarget, formatDay, getCiTarget, saveCiTarget, tokenState } from "../api/runRequests";
import { useUserNames } from "../lib/useUserNames";
import ConfirmButton from "./ConfirmButton";
import ErrorBanner from "./ErrorBanner";

const DEFAULT_WORKFLOW = "qa-vision-run.yml";
const DEFAULT_BRANCH = "main";

/** Owners and admins see this from 14 days before the token expires (Settings and the run panel). */
export function ExpiryWarning({ target }: { target: CiTarget }) {
  const state = tokenState(target);
  if (state === "ok" || !target.token_expires_at) return null;
  const day = formatDay(target.token_expires_at);
  return (
    <p className="note warn-note" role="note">
      <CircleAlert size={16} aria-hidden="true" />
      <span>
        {state === "expired"
          ? `The GitHub token expired on ${day}. Replace it in Settings`
          : `The GitHub token expires on ${day}. Replace it in Settings`}
      </span>
    </p>
  );
}

/** Settings › Run from QA Vision: the repository, workflow, branch and token Play dispatches with. */
export default function CiTargetCard({ projectId }: { projectId: number }) {
  const qc = useQueryClient();
  const queryKey = ["ci-target", projectId];
  const target = useQuery({ queryKey, queryFn: () => getCiTarget(projectId) });
  const nameOf = useUserNames(projectId);
  const [repo, setRepo] = useState("");
  const [workflow, setWorkflow] = useState(DEFAULT_WORKFLOW);
  const [ref, setRef] = useState(DEFAULT_BRANCH);
  const [token, setToken] = useState("");
  const [replacing, setReplacing] = useState(false);

  const data = target.data;
  useEffect(() => {
    if (!data) return;
    setRepo(data.repo ?? "");
    setWorkflow(data.workflow ?? DEFAULT_WORKFLOW);
    setRef(data.ref ?? DEFAULT_BRANCH);
    setToken("");
    setReplacing(false);
  }, [data]);

  const save = useMutation({
    mutationFn: () => saveCiTarget(projectId, {
      repo: repo.trim(), workflow: workflow.trim(), ref: ref.trim(), ...(token.trim() ? { token: token.trim() } : {}),
    }),
    onSuccess: (saved) => qc.setQueryData(queryKey, saved),
  });
  const disconnect = useMutation({
    mutationFn: () => deleteCiTarget(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  return (
    <div className="card">
      <h3>Run from QA Vision</h3>
      <p className="muted">
        Play runs the selected scenarios in this repository's GitHub Actions, through a dedicated workflow.
        QA Vision never runs test code itself.
      </p>
      {target.error != null && <ErrorBanner error={target.error} onRetry={() => target.refetch()} />}
      {target.isPending && <p className="muted">Loading…</p>}
      {data && !data.available && (
        <p className="note" role="note">
          Running tests from QA Vision is not configured on this server. An administrator sets{" "}
          <code>TM_SECRETS_KEY</code> on test-management-service.
        </p>
      )}
      {data?.available && (
        <>
          {data.configured && (
            <>
              <p className="success-note" role="status">
                <CheckCircle2 size={16} aria-hidden="true" />
                <span>
                  {`Connected: ${data.repo} · token …${data.token_last4} · `}
                  {data.token_expires_at ? `expires ${formatDay(data.token_expires_at)}` : "no expiry"}
                </span>
              </p>
              <ExpiryWarning target={data} />
            </>
          )}
          {data.last_change && (
            <p className="muted">{`Last changed by ${nameOf(data.last_change.user_id)} on ${formatDay(data.last_change.at)}`}</p>
          )}
          <form className="form-stack" onSubmit={onSubmit}>
            <label>
              Repository
              <input required value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="owner/name"
                pattern="[A-Za-z0-9\-]{1,39}/[A-Za-z0-9._\-]{1,100}" title="owner/name, as on github.com"
                autoComplete="off" spellCheck={false} />
            </label>
            <label>
              Workflow file
              <input required value={workflow} onChange={(e) => setWorkflow(e.target.value)} autoComplete="off" spellCheck={false} />
            </label>
            <label>
              Branch
              <input required value={ref} onChange={(e) => setRef(e.target.value)} autoComplete="off" spellCheck={false} />
            </label>
            {data.configured && !replacing ? (
              <div>
                <button type="button" onClick={() => setReplacing(true)}>Replace token</button>
              </div>
            ) : (
              <label>
                Token
                <input type="password" required={!data.configured} value={token} autoFocus={replacing}
                  onChange={(e) => setToken(e.target.value)} autoComplete="off" spellCheck={false} />
              </label>
            )}
            <div className="button-row">
              <button className="primary" type="submit" disabled={save.isPending}>
                {save.isPending ? "Checking with GitHub…" : "Save"}
              </button>
            </div>
          </form>
          {save.error != null && <ErrorBanner error={save.error} />}
          {data.configured && (
            <ConfirmButton
              label="Disconnect"
              question={`Disconnect ${data.repo}? Nobody can run tests from QA Vision until a token is saved again.`}
              confirmLabel="Disconnect"
              onConfirm={() => disconnect.mutate()}
              disabled={disconnect.isPending}
            />
          )}
          {disconnect.error != null && <ErrorBanner error={disconnect.error} />}
        </>
      )}
    </div>
  );
}
