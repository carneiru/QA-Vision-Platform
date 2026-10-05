import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useMatch, useNavigate } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  Building2, FileText, FlaskConical, FolderKanban, GitBranch, LayoutDashboard, ListChecks, LogOut, Menu,
  ScanSearch, Settings, ShieldCheck, Shuffle, TrendingUp, X,
} from "lucide-react";
import { logout } from "../api/auth";
import { getProject, listMyOrganizations, listProjects } from "../api/orgs";

const PROJECT_VIEWS = [
  { to: "overview", label: "Overview", icon: LayoutDashboard },
  { to: "runs", label: "Runs", icon: ListChecks },
  { to: "tests", label: "Tests", icon: FlaskConical },
  { to: "flaky", label: "Flaky", icon: Shuffle },
  { to: "branches", label: "Branches", icon: GitBranch },
  { to: "trends", label: "Trends", icon: TrendingUp },
  { to: "report", label: "Report", icon: FileText },
  { to: "settings", label: "Settings", icon: Settings },
];

const navClass = ({ isActive }: { isActive: boolean }) => (isActive ? "nav-link active" : "nav-link");

/** Authenticated frame: a sidebar with the project switcher and every view,
 *  which becomes a drawer behind a menu button on narrow screens. */
export default function AppShell() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const projectMatch = useMatch("/projects/:projectId/*");
  const projectId = projectMatch ? Number(projectMatch.params.projectId) : null;

  const orgs = useQuery({ queryKey: ["orgs"], queryFn: listMyOrganizations });
  const projectLists = useQueries({
    queries: (orgs.data ?? []).map((org) => ({
      queryKey: ["projects", org.id],
      queryFn: () => listProjects(org.id),
    })),
  });
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId!),
    enabled: projectId !== null,
  });

  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  const wasOpen = useRef(false);

  // A followed link closes the drawer
  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    if (open) {
      sidebar.current?.querySelector<HTMLElement>("select, a, button")?.focus();
    } else if (wasOpen.current) {
      menuButton.current?.focus();
    }
    wasOpen.current = open;
  }, [open]);

  async function onSignOut() {
    await logout();
    navigate("/login", { replace: true });
  }

  const orgId = project.data?.organization_id;

  return (
    <div className="shell">
      <header className="topbar">
        <button
          ref={menuButton}
          className="ghost"
          aria-label="Open navigation"
          aria-expanded={open}
          aria-controls="sidebar"
          onClick={() => setOpen(true)}
        >
          <Menu size={20} aria-hidden="true" />
        </button>
        <span className="brand">
          <ScanSearch size={18} aria-hidden="true" /> QA Vision
        </span>
      </header>

      <aside
        id="sidebar"
        ref={sidebar}
        className={open ? "sidebar open" : "sidebar"}
        aria-label="Navigation"
        onKeyDown={(e) => {
          if (e.key === "Escape" && open) setOpen(false);
        }}
      >
        <div className="brand brand-row">
          <span className="brand-mark">
            <ScanSearch size={18} aria-hidden="true" /> QA Vision
          </span>
          {open && (
            <button className="ghost" aria-label="Close navigation" onClick={() => setOpen(false)}>
              <X size={18} aria-hidden="true" />
            </button>
          )}
        </div>

        {orgs.data && orgs.data.length > 0 && (
          <div className="switcher">
            <label htmlFor="project-switcher">Project</label>
            <select
              id="project-switcher"
              value={projectId ?? ""}
              onChange={(e) => {
                if (e.target.value) navigate(`/projects/${e.target.value}/overview`);
              }}
            >
              {projectId === null && <option value="">Choose a project…</option>}
              {orgs.data.map((org, i) => (
                <optgroup key={org.id} label={org.name}>
                  {(projectLists[i]?.data ?? []).map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
        )}

        {projectId !== null && (
          <nav className="nav-section" aria-label="Project views">
            {PROJECT_VIEWS.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={`/projects/${projectId}/${to}`} className={navClass}>
                <Icon size={17} aria-hidden="true" /> {label}
              </NavLink>
            ))}
          </nav>
        )}

        <nav className="nav-section" aria-label="Workspace">
          <span className="nav-title">Workspace</span>
          <NavLink to="/" end className={navClass}>
            <FolderKanban size={17} aria-hidden="true" /> All projects
          </NavLink>
          {orgId !== undefined && (
            <NavLink to={`/organizations/${orgId}`} className={navClass}>
              <Building2 size={17} aria-hidden="true" /> Organization
            </NavLink>
          )}
        </nav>

        <div className="sidebar-footer">
          <NavLink to="/account/security" className={navClass}>
            <ShieldCheck size={17} aria-hidden="true" /> Security
          </NavLink>
          <button className="ghost" onClick={onSignOut}>
            <LogOut size={17} aria-hidden="true" /> Sign out
          </button>
        </div>
      </aside>
      <div className={open ? "backdrop open" : "backdrop"} onClick={() => setOpen(false)} aria-hidden="true" />

      <div className="shell-main">
        <main id="main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
