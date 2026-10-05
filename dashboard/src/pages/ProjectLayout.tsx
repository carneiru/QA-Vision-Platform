import { useEffect } from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getProject, listMyOrganizations } from "../api/orgs";
import { pageTitle, useFocusOnNavigate } from "../routeFocus";

const VIEW_TITLES: Record<string, string> = {
  overview: "Overview", trends: "Trends", tests: "Tests", flaky: "Flaky", branches: "Branches",
  runs: "Runs", report: "Report", settings: "Settings",
};

/** "runs/7" -> "Run #7", "tests/<key>" -> "Test history", "flaky" -> "Flaky" */
function viewTitle(rest: string): string {
  const [view, detail] = rest.split("/");
  if (view === "runs" && detail) return `Run #${detail}`;
  if (view === "tests" && detail) return "Test history";
  return VIEW_TITLES[view] ?? "Project";
}

/** Project frame inside the app shell: the project's name over its current view.
 *  Navigation between views lives in the sidebar. */
export default function ProjectLayout() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const project = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id) });
  const orgs = useQuery({ queryKey: ["orgs"], queryFn: listMyOrganizations });
  const location = useLocation();

  const projectName = project.data?.name;
  useEffect(() => {
    const rest = location.pathname.split("/").slice(3).join("/");
    document.title = pageTitle(viewTitle(rest), projectName ?? `Project ${projectId}`);
  }, [location.pathname, projectName, projectId]);
  useFocusOnNavigate();

  const orgName = orgs.data?.find((o) => o.id === project.data?.organization_id)?.name;

  return (
    <div className="page">
      <header className="view-head">
        <div>
          {orgName && <div className="crumb">{orgName}</div>}
          <h1>{projectName ?? `Project ${projectId}`}</h1>
        </div>
      </header>
      <div id="content" tabIndex={-1}>
        <Outlet />
      </div>
    </div>
  );
}
