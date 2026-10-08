import { Link, useLocation, useMatch, useNavigate } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { getProject, listMyOrganizations, listProjects } from "../api/orgs";
import { parentView, projectRest, viewTitle } from "../lib/viewTitle";

/** Pages outside a project, by path prefix */
const PAGES: [string, string][] = [
  ["/account/security", "Security"],
  ["/organizations/", "Organization"],
  ["/invitations/", "Invitation"],
];

/** Org / Project / Page, from the route. The project item is the project switcher. */
export default function Breadcrumb() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const projectMatch = useMatch("/projects/:projectId/*");
  const orgMatch = useMatch("/organizations/:orgId");
  const projectId = projectMatch ? Number(projectMatch.params.projectId) : null;

  const orgs = useQuery({ queryKey: ["orgs"], queryFn: listMyOrganizations });
  const projectLists = useQueries({
    queries: (projectId !== null ? orgs.data ?? [] : []).map((org) => ({
      queryKey: ["projects", org.id],
      queryFn: () => listProjects(org.id),
    })),
  });
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId!),
    enabled: projectId !== null,
  });

  let page: string;
  let section: { label: string; to: string } | null = null;
  if (projectId !== null) {
    const rest = projectRest(pathname);
    page = viewTitle(rest);
    const parent = parentView(rest);
    if (parent) section = { label: parent.label, to: `/projects/${projectId}/${parent.view}` };
  } else if (orgMatch) {
    page = orgs.data?.find((o) => o.id === Number(orgMatch.params.orgId))?.name ?? "Organization";
  } else {
    page = PAGES.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? "Projects";
  }

  const org = projectId !== null ? orgs.data?.find((o) => o.id === project.data?.organization_id) : undefined;

  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      <ol>
        {org && (
          <li>
            <Link to={`/organizations/${org.id}`}>{org.name}</Link>
          </li>
        )}
        {projectId !== null && (
          <li>
            {orgs.data && orgs.data.length > 0 ? (
              <>
                <label htmlFor="project-switcher" className="sr-only">Project</label>
                <select
                  id="project-switcher"
                  className="crumb-select"
                  value={projectId}
                  onChange={(e) => {
                    if (e.target.value) navigate(`/projects/${e.target.value}/overview`);
                  }}
                >
                  {/* The current project before the lists answer, so the select never shows a blank */}
                  {projectLists.every((q) => !q.data) && (
                    <option value={projectId}>{project.data?.name ?? `Project ${projectId}`}</option>
                  )}
                  {orgs.data.map((o, i) => (
                    <optgroup key={o.id} label={o.name}>
                      {(projectLists[i]?.data ?? []).map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </>
            ) : (
              <span>{project.data?.name ?? `Project ${projectId}`}</span>
            )}
          </li>
        )}
        {section && (
          <li>
            <Link to={section.to}>{section.label}</Link>
          </li>
        )}
        <li>
          <span aria-current="page">{page}</span>
        </li>
      </ol>
    </nav>
  );
}
