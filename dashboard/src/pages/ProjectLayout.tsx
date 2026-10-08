import { useEffect } from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getProject } from "../api/orgs";
import { pageTitle, useFocusOnNavigate } from "../routeFocus";
import { projectRest, viewTitle } from "../lib/viewTitle";

/** Project frame inside the app shell: sets the document title (view + project) around the current view.
 *  The org and project live in the top bar's breadcrumb; each view renders its own PageHeader. */
export default function ProjectLayout() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const project = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id) });
  const location = useLocation();

  const projectName = project.data?.name;
  useEffect(() => {
    document.title = pageTitle(viewTitle(projectRest(location.pathname)), projectName ?? `Project ${projectId}`);
  }, [location.pathname, projectName, projectId]);
  useFocusOnNavigate();

  return (
    <div className="page">
      <div id="content" tabIndex={-1}>
        <Outlet />
      </div>
    </div>
  );
}
