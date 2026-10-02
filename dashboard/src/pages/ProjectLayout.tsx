import { Link, NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { logout } from "../api/auth";
import { getProject } from "../api/orgs";

export default function ProjectLayout() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const project = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id) });
  const navigate = useNavigate();

  async function onSignOut() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>{project.data?.name ?? `Project ${projectId}`}</h1>
        <span>
          <Link to="/">Switch project</Link>{" "}
          <button onClick={onSignOut}>Sign out</button>
        </span>
      </div>
      <nav className="tabs" aria-label="Project views">
        <NavLink to="trends" className={({ isActive }) => (isActive ? "active" : "")}>Trends</NavLink>
        <NavLink to="tests" end className={({ isActive }) => (isActive ? "active" : "")}>Tests</NavLink>
        <NavLink to="flaky" className={({ isActive }) => (isActive ? "active" : "")}>Flaky</NavLink>
      </nav>
      <Outlet />
    </div>
  );
}
