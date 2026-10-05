import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, CircleHelp, ExternalLink } from "lucide-react";
import {
  Repository,
  VerificationStatus,
  addRepository,
  listRepositories,
  removeRepository,
  verifyRepository,
} from "../api/repositories";
import ConfirmButton from "./ConfirmButton";
import ErrorBanner from "./ErrorBanner";

const PROVIDERS: Record<string, string> = { github: "GitHub", gitlab: "GitLab", azure_devops: "Azure DevOps" };

const STATUS: Record<VerificationStatus, { label: string; className: string; Icon: typeof CheckCircle2; hint: string }> = {
  verified: {
    label: "Reachable",
    className: "badge badge-passed",
    Icon: CheckCircle2,
    hint: "The provider confirmed this repository exists.",
  },
  not_found: {
    label: "Not found or private",
    className: "badge badge-warn",
    Icon: CircleAlert,
    hint: "The check runs without signing in, so a private repository looks the same as a missing one.",
  },
  unchecked: {
    label: "Not checked",
    className: "badge badge-muted",
    Icon: CircleHelp,
    hint: "The provider could not be reached or was rate-limiting. Check again later.",
  },
};

function StatusBadge({ status }: { status: VerificationStatus }) {
  const s = STATUS[status] ?? STATUS.unchecked;
  return (
    <span className={s.className} title={s.hint}>
      <s.Icon size={14} aria-hidden="true" /> {s.label}
    </span>
  );
}

interface Props {
  projectId: number;
  /** Owners, admins and members may change repositories; viewers only read.
   *  Undefined while the role is loading: the list shows, the controls wait. */
  canEdit: boolean | undefined;
}

export default function RepositoriesCard({ projectId, canEdit }: Props) {
  const qc = useQueryClient();
  const queryKey = ["repositories", projectId];
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");

  const repos = useQuery({ queryKey, queryFn: () => listRepositories(projectId) });
  const refresh = () => qc.invalidateQueries({ queryKey });

  const add = useMutation({
    mutationFn: () => addRepository(projectId, url.trim(), branch.trim() || undefined),
    onSuccess: () => {
      setUrl("");
      setBranch("");
      return refresh();
    },
  });
  const verify = useMutation({
    mutationFn: (repoId: number) => verifyRepository(projectId, repoId),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (repoId: number) => removeRepository(projectId, repoId),
    onSuccess: refresh,
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    add.mutate();
  }

  const fullName = (r: Repository) => `${r.owner}/${r.name}`;

  return (
    <div className="card">
      <h3>Repositories</h3>
      <p className="muted">
        Where this project's test code lives, on github.com, gitlab.com or Azure DevOps. Paste
        the address from the browser or a clone URL.
      </p>

      {canEdit === undefined ? null : canEdit ? (
        <form className="inline-form" onSubmit={onSubmit}>
          <label className="grow">
            Repository URL
            <input
              required
              inputMode="url"
              autoComplete="off"
              spellCheck={false}
              placeholder="https://github.com/acme/e2e-tests"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>
          <label>
            <span>
              Default branch <span className="muted">(optional)</span>
            </span>
            <input
              autoComplete="off"
              spellCheck={false}
              placeholder="from the provider"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
            />
          </label>
          <button type="submit" disabled={add.isPending}>
            {add.isPending ? "Adding…" : "Add repository"}
          </button>
        </form>
      ) : (
        <p className="muted">Only owners, admins and members can add or remove repositories.</p>
      )}
      {add.error != null && <ErrorBanner error={add.error} />}
      {verify.error != null && <ErrorBanner error={verify.error} />}
      {remove.error != null && <ErrorBanner error={remove.error} />}

      {repos.error != null && <ErrorBanner error={repos.error} onRetry={() => repos.refetch()} />}
      {repos.isPending && <p className="muted">Loading repositories…</p>}
      {repos.data?.length === 0 && (
        <p className="muted">
          No repositories yet.{canEdit && " Add the one your test suite lives in."}
        </p>
      )}
      {repos.data != null && repos.data.length > 0 && (
        <table className="data">
          <thead>
            <tr>
              <th>Repository</th>
              <th className="hide-narrow">Provider</th>
              <th>Default branch</th>
              <th>Status</th>
              {canEdit && <th><span className="sr-only">Actions</span></th>}
            </tr>
          </thead>
          <tbody>
            {repos.data.map((r) => (
              <tr key={r.id}>
                <td className="wrap-anywhere">
                  <a href={r.url} target="_blank" rel="noopener noreferrer" className="link-arrow">
                    {fullName(r)}
                    <ExternalLink size={13} aria-hidden="true" />
                    <span className="sr-only"> (opens in a new tab)</span>
                  </a>
                </td>
                <td className="hide-narrow">{PROVIDERS[r.provider] ?? r.provider}</td>
                <td><code>{r.default_branch}</code></td>
                <td><StatusBadge status={r.verification_status} /></td>
                {canEdit && (
                  <td className="row-actions">
                    <button
                      aria-label={`Check ${fullName(r)} again`}
                      onClick={() => verify.mutate(r.id)}
                      disabled={verify.isPending && verify.variables === r.id}
                    >
                      {verify.isPending && verify.variables === r.id ? "Checking…" : "Check again"}
                    </button>
                    <ConfirmButton
                      label="Remove"
                      ariaLabel={`Remove ${fullName(r)}`}
                      question={`Remove ${fullName(r)} from this project? Test results already sent are kept.`}
                      confirmLabel="Remove"
                      onConfirm={() => remove.mutate(r.id)}
                      disabled={remove.isPending}
                    />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
