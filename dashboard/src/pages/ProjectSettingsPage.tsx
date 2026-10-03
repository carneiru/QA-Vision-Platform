import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiKeyCreated, createKey, listKeys, revokeKey } from "../api/keys";
import ErrorBanner from "../components/ErrorBanner";

export default function ProjectSettingsPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const keys = useQuery({ queryKey: ["keys", id], queryFn: () => listKeys(id) });

  const create = useMutation({
    mutationFn: () => createKey(id, name.trim()),
    onSuccess: (key) => {
      setCreated(key);
      setCopied(false);
      setName("");
      qc.invalidateQueries({ queryKey: ["keys", id] });
    },
  });
  const revoke = useMutation({
    mutationFn: (keyId: number) => revokeKey(id, keyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keys", id] }),
  });

  async function copyKey(key: string) {
    try {
      await navigator.clipboard.writeText(key);
      setCopied(true);
    } catch {
      setCopied(false); // clipboard blocked: the key stays selectable
    }
  }

  return (
    <section>
      <h2 className="sr-only">Project settings</h2>
      <div className="card">
        <h3>API keys</h3>
        <p className="muted">
          The collector authenticates uploads with a project API key, sent as the{" "}
          <code>QAV_API_KEY</code> environment variable in CI.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          style={{ display: "flex", gap: 8, alignItems: "end", flexWrap: "wrap", marginBottom: 12 }}
        >
          <label>
            Name
            <input required placeholder="e.g. github-actions" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <button type="submit" disabled={create.isPending}>Create key</button>
        </form>
        {create.error != null && <ErrorBanner error={create.error} />}
        {revoke.error != null && <ErrorBanner error={revoke.error} />}
        {created && (
          <p role="status">
            Key <strong>{created.name}</strong> — store it now (only shown once):{" "}
            <code>{created.key}</code>{" "}
            <button aria-label={`Copy the API key ${created.name}`} onClick={() => copyKey(created.key)}>
              {copied ? "Copied" : "Copy key"}
            </button>
          </p>
        )}

        {keys.error != null && <ErrorBanner error={keys.error} onRetry={() => keys.refetch()} />}
        {keys.isPending && <p className="muted">Loading keys…</p>}
        {keys.data?.length === 0 && <p className="muted">No API keys yet — create one to start uploading.</p>}
        {keys.data != null && keys.data.length > 0 && (
          <table className="data">
            <thead>
              <tr>
                <th>Name</th><th>Key</th><th>Created</th><th>Last used</th>
                <th><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {keys.data.map((key) => (
                <tr key={key.id}>
                  <td>{key.name}</td>
                  <td><code>{key.key_prefix}…</code></td>
                  <td>{new Date(key.created_at).toLocaleDateString()}</td>
                  <td>{key.last_used_at ? new Date(key.last_used_at).toLocaleString() : "—"}</td>
                  <td>
                    {key.revoked_at ? (
                      <span className="muted">revoked</span>
                    ) : (
                      <button
                        aria-label={`Revoke key ${key.name}`}
                        onClick={() => revoke.mutate(key.id)}
                        disabled={revoke.isPending}
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
