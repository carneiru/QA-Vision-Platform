import { useEffect, useRef } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { logout } from "../api/auth";
import { getProject } from "../api/orgs";

export default function ProjectLayout() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const project = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id) });
  const navigate = useNavigate();
  const location = useLocation();
  const tabs = useRef<HTMLElement>(null);

  // On narrow screens the tab strip scrolls; keep the current view's tab in sight
  useEffect(() => {
    tabs.current?.querySelector(".active")?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
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
      <Outlet />
    </div>
  );
}
