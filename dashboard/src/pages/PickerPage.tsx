import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listMyOrganizations, listProjects } from "../api/orgs";
import ErrorBanner from "../components/ErrorBanner";

export default function PickerPage() {
  const [orgId, setOrgId] = useState<number | null>(null);
  const orgs = useQuery({ queryKey: ["orgs"], queryFn: listMyOrganizations });
  const projects = useQuery({
    queryKey: ["projects", orgId],
    queryFn: () => listProjects(orgId!),
    enabled: orgId !== null,
  });

  return (
    <div className="page">
      <h1>Choose a project</h1>
      {orgs.error != null && <ErrorBanner error={orgs.error} onRetry={() => orgs.refetch()} />}
      {orgs.isPending && <p className="muted">Loading organizations…</p>}
      {orgs.data?.length === 0 && (
        <p className="muted">You are not a member of any organization yet.</p>
      )}
      <div style={{ display: "flex", gap: 24 }}>
        <ul>
          {orgs.data?.map((org) => (
            <li key={org.id}>
              <button onClick={() => setOrgId(org.id)}>{org.name}</button>{" "}
              <span className="muted">{org.role}</span>
            </li>
          ))}
        </ul>
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
          </div>
        )}
      </div>
    </div>
  );
}
