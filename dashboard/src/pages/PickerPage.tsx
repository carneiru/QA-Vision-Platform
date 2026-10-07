import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderKanban, Plus } from "lucide-react";
import {
  MyOrganization, createOrganization, createProject, listMyOrganizations, listProjects, slugify,
} from "../api/orgs";
import ErrorBanner from "../components/ErrorBanner";

const MANAGER_ROLES = ["owner", "admin"];

/** One organization: its projects as tiles, and project creation for its managers. */
function OrgProjects({ org }: { org: MyOrganization }) {
  const qc = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [name, setName] = useState("");
  const projects = useQuery({ queryKey: ["projects", org.id], queryFn: () => listProjects(org.id) });
  const create = useMutation({
    mutationFn: () => createProject(org.id, name.trim()),
    onSuccess: () => {
      setFormOpen(false);
      setName("");
      qc.invalidateQueries({ queryKey: ["projects", org.id] });
    },
  });
  const canCreate = MANAGER_ROLES.includes(org.role);

  return (
    <section className="org-block" aria-labelledby={`org-${org.id}`}>
      <div className="org-block-head">
        <div>
          <h2 id={`org-${org.id}`}>{org.name}</h2>
          <span className="muted">
            Your role: {org.role} · <Link className="inline-link" to={`/organizations/${org.id}`}>Members and invitations</Link>
          </span>
        </div>
        {canCreate && !formOpen && (
          <button onClick={() => setFormOpen(true)}>
            <Plus size={16} aria-hidden="true" /> New project
          </button>
        )}
      </div>

      {canCreate && formOpen && (
        <form
          className="card inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <label>
            Project name
            <input required autoFocus value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <button className="primary" type="submit" disabled={create.isPending}>Create project</button>
          <button type="button" onClick={() => setFormOpen(false)}>Cancel</button>
          {create.error != null && <ErrorBanner error={create.error} />}
        </form>
      )}

      {projects.error != null && <ErrorBanner error={projects.error} onRetry={() => projects.refetch()} />}
      {projects.isPending && <p className="muted">Loading projects…</p>}
      {projects.data?.length === 0 && (
        <p className="muted">No projects in this organization{canCreate ? " yet — create the first one." : "."}</p>
      )}
      {projects.data != null && projects.data.length > 0 && (
        <div className="project-grid">
          {projects.data.map((project) => (
            <Link key={project.id} className="project-tile" to={`/projects/${project.id}/overview`}>
              <FolderKanban size={18} aria-hidden="true" /> {project.name}
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

export default function PickerPage() {
  const qc = useQueryClient();
  const [orgFormOpen, setOrgFormOpen] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);

  const orgs = useQuery({ queryKey: ["orgs"], queryFn: listMyOrganizations });
  const createOrg = useMutation({
    mutationFn: () => createOrganization(orgName.trim(), orgSlug),
    onSuccess: () => {
      setOrgFormOpen(false);
      setOrgName("");
      setOrgSlug("");
      setSlugEdited(false);
      qc.invalidateQueries({ queryKey: ["orgs"] });
    },
  });

  return (
    <div className="page">
      <header className="view-head">
        <h1>Projects</h1>
        {!orgFormOpen && (
          <button onClick={() => setOrgFormOpen(true)}>
            <Plus size={16} aria-hidden="true" /> New organization
          </button>
        )}
      </header>

      {orgFormOpen && (
        <form
          className="card inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            createOrg.mutate();
          }}
        >
          <label>
            Name
            <input
              required
              autoFocus
              value={orgName}
              onChange={(e) => {
                setOrgName(e.target.value);
                if (!slugEdited) setOrgSlug(slugify(e.target.value));
              }}
            />
          </label>
          <label>
            Slug
            <input
              required
              pattern="[a-z0-9-]+"
              value={orgSlug}
              onChange={(e) => {
                setSlugEdited(true);
                setOrgSlug(e.target.value);
              }}
            />
          </label>
          <button className="primary" type="submit" disabled={createOrg.isPending}>Create organization</button>
          <button type="button" onClick={() => setOrgFormOpen(false)}>Cancel</button>
          {createOrg.error != null && <ErrorBanner error={createOrg.error} />}
        </form>
      )}

      {orgs.error != null && <ErrorBanner error={orgs.error} onRetry={() => orgs.refetch()} />}
      {orgs.isPending && <p className="muted">Loading organizations…</p>}
      {orgs.data?.length === 0 && !orgFormOpen && (
        <div className="card">
          <h2>Welcome to QEOS</h2>
          <p className="muted">
            You are not a member of any organization yet. Create one to start a project, or open
            the invitation link a teammate sent you.
          </p>
        </div>
      )}
      {orgs.data?.map((org) => <OrgProjects key={org.id} org={org} />)}
    </div>
  );
}
