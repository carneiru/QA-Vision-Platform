import { useEffect, useRef } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { logout } from "../api/auth";
import { getProject } from "../api/orgs";
import { pageTitle, useFocusOnNavigate } from "../routeFocus";

const VIEW_TITLES: Record<string, string> = {
  trends: "Trends", tests: "Tests", flaky: "Flaky", branches: "Branches", runs: "Runs", settings: "Settings",
};

/** "runs/7" -> "Run #7", "tests/<key>" -> "Test history", "flaky" -> "Flaky" */
function viewTitle(rest: string): string {
  const [view, detail] = rest.split("/");
  if (view === "runs" && detail) return `Run #${detail}`;
  if (view === "tests" && detail) return "Test history";
  return VIEW_TITLES[view] ?? "Project";
}


export default function ProjectLayout() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const project = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id) });
  const navigate = useNavigate();
  const location = useLocation();
  const tabs = useRef<HTMLElement>(null);

  const projectName = project.data?.name;
  useEffect(() => {
    const rest = location.pathname.split("/").slice(3).join("/");
    document.title = pageTitle(viewTitle(rest), projectName ?? `Project ${projectId}`);
  }, [location.pathname, projectName, projectId]);
  useFocusOnNavigate();

  // On narrow screens the tab strip scrolls; keep the current view's tab in sight.
  // Scroll the strip itself: scrollIntoView moves Chrome's keyboard starting
  // point into the page, so the first Tab would skip the skip link and the tabs.
  useEffect(() => {
    const strip = tabs.current;
    const active = strip?.querySelector<HTMLElement>(".active");
    if (!strip || !active) return;
    const s = strip.getBoundingClientRect();
    const a = active.getBoundingClientRect();
    if (a.right > s.right) strip.scrollLeft += a.right - s.right;
    else if (a.left < s.left) strip.scrollLeft -= s.left - a.left;
  }, [location.pathname]);

  async function onSignOut() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{project.data?.name ?? `Project ${projectId}`}</h1>
        <span>
          <Link to="/">Switch project</Link>
          <Link to="/account/security">Security</Link>
          <button onClick={onSignOut}>Sign out</button>
        </span>
      </div>
      <nav ref={tabs} className="tabs" aria-label="Project views">
        <NavLink to="trends" className={({ isActive }) => (isActive ? "active" : "")}>Trends</NavLink>
        <NavLink to="tests" end className={({ isActive }) => (isActive ? "active" : "")}>Tests</NavLink>
        <NavLink to="flaky" className={({ isActive }) => (isActive ? "active" : "")}>Flaky</NavLink>
        <NavLink to="branches" className={({ isActive }) => (isActive ? "active" : "")}>Branches</NavLink>
        <NavLink to="runs" className={({ isActive }) => (isActive ? "active" : "")}>Runs</NavLink>
        <NavLink to="settings" className={({ isActive }) => (isActive ? "active" : "")}>Settings</NavLink>
      </nav>
      <div id="content" tabIndex={-1}>
        <Outlet />
      </div>
    </div>
  );
}
