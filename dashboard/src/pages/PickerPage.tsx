import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { logout } from "../api/auth";
import { createOrganization, createProject, listMyOrganizations, listProjects, slugify } from "../api/orgs";
import ErrorBanner from "../components/ErrorBanner";

const MANAGER_ROLES = ["owner", "admin"];

export default function PickerPage() {
  const [orgId, setOrgId] = useState<number | null>(null);
  const [orgFormOpen, setOrgFormOpen] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [projectFormOpen, setProjectFormOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const navigate = useNavigate();
  const qc = useQueryClient();

  async function onSignOut() {
    await logout();
    navigate("/login", { replace: true });
  }
  const orgs = useQuery({ queryKey: ["orgs"], queryFn: listMyOrganizations });
  const projects = useQuery({
    queryKey: ["projects", orgId],
    queryFn: () => listProjects(orgId!),
    enabled: orgId !== null,
  });

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
  const createProj = useMutation({
    mutationFn: () => createProject(orgId!, projectName.trim()),
    onSuccess: () => {
      setProjectFormOpen(false);
      setProjectName("");
      qc.invalidateQueries({ queryKey: ["projects", orgId] });
    },
  });

  const selected = orgs.data?.find((o) => o.id === orgId);
  const canCreateProject = selected != null && MANAGER_ROLES.includes(selected.role);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Choose a project</h1>
        <span>
          <Link to="/account/security">Security</Link>
          <button onClick={onSignOut}>Sign out</button>
        </span>
      </div>
      {orgs.error != null && <ErrorBanner error={orgs.error} onRetry={() => orgs.refetch()} />}
      {orgs.isPending && <p className="muted">Loading organizations…</p>}
      {orgs.data?.length === 0 && (
        <p className="muted">You are not a member of any organization yet.</p>
      )}
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <div>
          <ul>
            {orgs.data?.map((org) => (
              <li key={org.id}>
                <button onClick={() => setOrgId(org.id)}>{org.name}</button>{" "}
                <span className="muted">{org.role}</span>{" "}
                <Link to={`/organizations/${org.id}`}>Manage</Link>
              </li>
            ))}
          </ul>
          {orgFormOpen ? (
            <form
              className="card"
              onSubmit={(e) => {
                e.preventDefault();
                createOrg.mutate();
              }}
              style={{ display: "flex", gap: 8, alignItems: "end", flexWrap: "wrap" }}
            >
              <label>
                Name
                <input
                  required
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
              <button type="submit" disabled={createOrg.isPending}>Create organization</button>
              {createOrg.error != null && <ErrorBanner error={createOrg.error} />}
            </form>
          ) : (
            <button onClick={() => setOrgFormOpen(true)}>New organization</button>
          )}
        </div>
        {orgId !== null && (
          <div>
            {projects.error != null && (
              <ErrorBanner error={projects.error} onRetry={() => projects.refetch()} />
            )}
            {projects.isPending && <p className="muted">Loading projects…</p>}
            {projects.data?.length === 0 && <p className="muted">No projects in this organization.</p>}
            <ul>
              {projects.data?.map((project) => (
                <li key={project.id}>
                  <Link to={`/projects/${project.id}/trends`}>{project.name}</Link>
                </li>
              ))}
            </ul>
            {canCreateProject &&
              (projectFormOpen ? (
                <form
                  className="card"
                  onSubmit={(e) => {
                    e.preventDefault();
                    createProj.mutate();
                  }}
                  style={{ display: "flex", gap: 8, alignItems: "end", flexWrap: "wrap" }}
                >
                  <label>
                    Project name
                    <input required value={projectName} onChange={(e) => setProjectName(e.target.value)} />
                  </label>
                  <button type="submit" disabled={createProj.isPending}>Create project</button>
                  {createProj.error != null && <ErrorBanner error={createProj.error} />}
                </form>
              ) : (
                <button onClick={() => setProjectFormOpen(true)}>New project</button>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
