import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiKeyCreated, createKey, listKeys, revokeKey } from "../api/keys";
import ConfirmButton from "../components/ConfirmButton";
import ErrorBanner from "../components/ErrorBanner";

const COLLECTOR_REF = "collector-v0.1.0";

// Ready-to-paste CI wiring; the key itself always travels as a CI secret
function ciSnippets(origin: string): Record<string, { label: string; code: string }> {
  return {
    github: {
      label: "GitHub Actions",
      code: `# .github/workflows/tests.yml — after the test step
- uses: carneiru/QA-Vision-Platform/collector-action@${COLLECTOR_REF}
  if: always()   # report results even when tests failed
  with:
    url: ${origin}
    patterns: "reports/**/*.xml"
  env:
    QAV_API_KEY: \${{ secrets.QAV_API_KEY }}`,
    },
    gitlab: {
      label: "GitLab CI",
      code: `# .gitlab-ci.yml — set QAV_API_KEY as a masked CI/CD variable
include:
  - remote: https://raw.githubusercontent.com/carneiru/QA-Vision-Platform/${COLLECTOR_REF}/templates/qav-collector.gitlab-ci.yml

qav-collector-upload:
  variables:
    QAV_URL: ${origin}
    QAV_PATTERNS: "reports/**/*.xml"`,
    },
    jenkins: {
      label: "Jenkins",
      code: `// Jenkinsfile — needs the qa-vision shared library (collector-jenkins/)
withCredentials([string(credentialsId: 'qav-api-key', variable: 'QAV_API_KEY')]) {
  withEnv(['QAV_URL=${origin}']) {
    qavCollectorUpload(patterns: 'reports/**/*.xml')
  }
}`,
    },
    cli: {
      label: "Any machine (CLI)",
      code: `pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@${COLLECTOR_REF}#subdirectory=collector"
QAV_URL=${origin} QAV_API_KEY=<your key> qav-collector upload "reports/**/*.xml"`,
    },
  };
}

export default function ProjectSettingsPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [platform, setPlatform] = useState("github");
  const [snippetCopied, setSnippetCopied] = useState(false);
  const snippets = useMemo(() => ciSnippets(window.location.origin), []);

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
          className="inline-form"
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
                      <ConfirmButton
                        label="Revoke"
                        ariaLabel={`Revoke key ${key.name}`}
                        question={`Revoke key ${key.name}? Uploads using it stop working immediately.`}
                        confirmLabel="Revoke"
                        onConfirm={() => revoke.mutate(key.id)}
                        disabled={revoke.isPending}
                      />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3>Wire up your CI</h3>
        <p className="muted">
          Paste this after your test step; store the API key as a CI secret named{" "}
          <code>QAV_API_KEY</code>.
        </p>
        <label>
          CI platform
          <select value={platform} onChange={(e) => { setPlatform(e.target.value); setSnippetCopied(false); }}>
            {Object.entries(snippets).map(([value, s]) => (
              <option key={value} value={value}>{s.label}</option>
            ))}
          </select>
        </label>
        <pre data-testid="ci-snippet" className="code-block">
          <code>{snippets[platform].code}</code>
        </pre>
        <button
          aria-label="Copy the CI snippet"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(snippets[platform].code);
              setSnippetCopied(true);
            } catch {
              setSnippetCopied(false); // clipboard blocked: the snippet stays selectable
            }
          }}
        >
          {snippetCopied ? "Copied" : "Copy snippet"}
        </button>
      </div>
    </section>
  );
}
