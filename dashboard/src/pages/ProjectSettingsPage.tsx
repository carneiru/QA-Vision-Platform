import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiKeyCreated, createKey, listKeys, revokeKey } from "../api/keys";
import { getProject } from "../api/orgs";
import ConfirmButton from "../components/ConfirmButton";
import ErrorBanner from "../components/ErrorBanner";
import DataCard from "../components/DataCard";
import MaskingCard from "../components/MaskingCard";
import NotificationsCard from "../components/NotificationsCard";
import RepositoriesCard from "../components/RepositoriesCard";

const COLLECTOR_REF = "collector-v0.3.0";

// Mirrors EDIT_ROLES in platforms/project-service/src/project/api/deps.py
const EDIT_ROLES = ["owner", "admin", "member"];
const MANAGE_ROLES = ["owner", "admin"];

const LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]"];

/** True when this page is served from the user's own machine: hosted CI runners cannot reach it. */
export function isLocalOrigin(origin: string): boolean {
  try {
    return LOCAL_HOSTS.includes(new URL(origin).hostname);
  } catch {
    return false;
  }
}

// Platforms whose default runners live on the vendor's servers, never on this machine
const HOSTED_RUNNERS = ["github", "gitlab", "azure"];

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
    QAV_API_KEY: \${{ secrets.QAV_API_KEY }}

- name: Sync test cases from .feature files   # runs on master only (QAV_IMPORT_BRANCH to change)
  run: |
    pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@${COLLECTOR_REF}#subdirectory=collector"
    qav-collector import-features "tests/features/**/*.feature"
  env:
    QAV_URL: ${origin}
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
    QAV_PATTERNS: "reports/**/*.xml"

# syncs test cases from .feature files; runs on master only (set QAV_IMPORT_BRANCH to change)
qav-import-features:
  image: python:3.12
  script:
    - pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@${COLLECTOR_REF}#subdirectory=collector"
    - qav-collector import-features "tests/features/**/*.feature"
  variables:
    QAV_URL: ${origin}   # QAV_API_KEY comes from the masked CI/CD variable`,
    },
    azure: {
      label: "Azure Pipelines",
      code: `# azure-pipelines.yml — after the test step; add QAV_API_KEY as a secret pipeline variable
- script: |
    pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@${COLLECTOR_REF}#subdirectory=collector"
    qav-collector upload "reports/**/*.xml"
  displayName: Upload test results to QA Vision
  condition: always()      # report results even when tests failed
  continueOnError: true    # a failed upload does not fail the pipeline
  env:
    QAV_URL: ${origin}
    QAV_API_KEY: $(QAV_API_KEY)   # secret variables reach scripts only when mapped here

# syncs test cases from .feature files; runs on master only (set QAV_IMPORT_BRANCH to change)
- script: |
    pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@${COLLECTOR_REF}#subdirectory=collector"
    qav-collector import-features "tests/features/**/*.feature"
  displayName: Sync test cases from .feature files
  env:
    QAV_URL: ${origin}
    QAV_API_KEY: $(QAV_API_KEY)`,
    },
    jenkins: {
      label: "Jenkins",
      code: `// Jenkinsfile — needs the qa-vision shared library (collector-jenkins/)
withCredentials([string(credentialsId: 'qav-api-key', variable: 'QAV_API_KEY')]) {
  withEnv(['QAV_URL=${origin}']) {
    qavCollectorUpload(patterns: 'reports/**/*.xml', ref: '${COLLECTOR_REF}')
    // syncs test cases from .feature files; runs on master only (set QAV_IMPORT_BRANCH to change)
    // reuses the .qav-venv that qavCollectorUpload creates, so keep it after the upload step
    sh '''
      .qav-venv/bin/python -m qav_collector import-features "tests/features/**/*.feature"
    '''
  }
}`,
    },
    cli: {
      label: "Any machine (CLI)",
      code: isLocalOrigin(origin)
        ? `pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@${COLLECTOR_REF}#subdirectory=collector"
# The local stack uses a self-signed certificate; from the QA-Vision-Platform folder:
docker compose cp gateway:/etc/nginx/certs/tls.crt qav-ca.crt
QAV_URL=${origin} QAV_API_KEY=<your key> qav-collector upload "reports/**/*.xml" --ca-file qav-ca.crt
# syncs test cases from .feature files; runs on master only (set QAV_IMPORT_BRANCH to change)
QAV_URL=${origin} QAV_API_KEY=<your key> qav-collector import-features "tests/features/**/*.feature" --ca-file qav-ca.crt`
        : `pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@${COLLECTOR_REF}#subdirectory=collector"
QAV_URL=${origin} QAV_API_KEY=<your key> qav-collector upload "reports/**/*.xml"
# syncs test cases from .feature files; runs on master only (set QAV_IMPORT_BRANCH to change)
QAV_URL=${origin} QAV_API_KEY=<your key> qav-collector import-features "tests/features/**/*.feature"`,
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
  const local = isLocalOrigin(window.location.origin);
  const [platform, setPlatform] = useState(local ? "cli" : "github");
  const [snippetCopied, setSnippetCopied] = useState(false);
  const snippets = useMemo(() => ciSnippets(window.location.origin), []);

  const keys = useQuery({ queryKey: ["keys", id], queryFn: () => listKeys(id) });
  // Same key as ProjectLayout, so this is served from its cache
  const project = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id) });
  const canEdit = EDIT_ROLES.includes(project.data?.my_role ?? "");

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
      <RepositoriesCard projectId={id} canEdit={project.data == null ? undefined : canEdit} />
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
          {platform === "cli" ? (
            <>Run this on any machine with Python 3.9+, from the folder holding your test reports.</>
          ) : (
            <>
              Paste this after your test step; store the API key as a CI secret named{" "}
              <code>QAV_API_KEY</code>.
            </>
          )}
        </p>
        <label>
          CI platform
          <select value={platform} onChange={(e) => { setPlatform(e.target.value); setSnippetCopied(false); }}>
            {Object.entries(snippets).map(([value, s]) => (
              <option key={value} value={value}>{s.label}</option>
            ))}
          </select>
        </label>
        {local && HOSTED_RUNNERS.includes(platform) && (
          <p role="note" className="note">
            Hosted {snippets[platform].label} runners cannot reach localhost, where this page is
            served from. Use the CLI on this machine, a self-hosted runner here (add{" "}
            <code>--ca-file</code> for the self-signed certificate), or a deployment with a public address.
          </p>
        )}
        <pre data-testid="ci-snippet" className="code-block" tabIndex={0} aria-label="CI configuration">
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

      <MaskingCard projectId={id} canEdit={project.data == null ? undefined : canEdit} />
      {project.data != null && (
        <NotificationsCard projectId={id} projectName={project.data.name} canEdit={canEdit} />
      )}
      {project.data != null && (
        <DataCard project={project.data} canManage={MANAGE_ROLES.includes(project.data.my_role ?? "")} />
      )}
    </section>
  );
}
