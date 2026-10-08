import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useMatch, useNavigate } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  Building2, ClipboardList, FileText, FlaskConical, FolderKanban, GitBranch, LayoutDashboard, ListChecks, LogOut, Menu,
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
  { to: "cases", label: "Test cases", icon: ClipboardList },
  { to: "settings", label: "Settings", icon: Settings },
];

const NARROW_QUERY = "(max-width: 900px)";

/** True while the sidebar is a drawer (the CSS breakpoint); false where matchMedia is unavailable. */
function useDrawerLayout(): boolean {
  const [narrow, setNarrow] = useState(() => typeof window.matchMedia === "function" && window.matchMedia(NARROW_QUERY).matches);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(NARROW_QUERY);
    const onChange = () => setNarrow(mq.matches);
    onChange();
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, []);
  return narrow;
}

const FOCUSABLE = "a[href], button:not(:disabled), select:not(:disabled), input:not(:disabled)";

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
  const drawerLayout = useDrawerLayout();

  // Focus goes back to the menu button only when the reader closes the drawer. A followed link closes it too,
  // but then the new page's content takes focus (routeFocus): the button must not take it back.
  const focusMenuOnClose = useRef(true);
  const closeForNavigation = () => {
    focusMenuOnClose.current = false;
    setOpen(false);
  };
  useEffect(() => closeForNavigation(), [pathname]);
  // The layout widened past the drawer breakpoint while it was open: it is a plain sidebar again
  const wasDrawer = useRef(drawerLayout);
  useEffect(() => {
    if (wasDrawer.current && !drawerLayout && open) closeForNavigation();
    wasDrawer.current = drawerLayout;
  }, [drawerLayout, open]);

  useEffect(() => {
    if (open) {
      focusMenuOnClose.current = true;
      sidebar.current?.querySelector<HTMLElement>("a[href]")?.focus();
    } else if (wasOpen.current && focusMenuOnClose.current) {
      menuButton.current?.focus();
    }
    wasOpen.current = open;
  }, [open]);

  // Escape closes the open drawer from wherever focus is, not only from inside it
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // A closed drawer is off-screen, not gone: inert + aria-hidden keep Tab and screen readers out of it
  useEffect(() => {
    const el = sidebar.current;
    if (!el) return;
    if (drawerLayout && !open) {
      el.setAttribute("inert", "");
      el.setAttribute("aria-hidden", "true");
    } else {
      el.removeAttribute("inert");
      el.removeAttribute("aria-hidden");
    }
  }, [drawerLayout, open]);

  // The open drawer is modal: Tab cycles inside it
  function trapTab(e: React.KeyboardEvent<HTMLElement>) {
    const items = Array.from(sidebar.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

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
          <ScanSearch size={18} aria-hidden="true" /> QEOS
        </span>
      </header>

      <aside
        id="sidebar"
        ref={sidebar}
        className={open ? "sidebar open" : "sidebar"}
        aria-label="Navigation"
        role={open && drawerLayout ? "dialog" : undefined}
        aria-modal={open && drawerLayout ? true : undefined}
        onKeyDown={(e) => {
          if (open && drawerLayout && e.key === "Tab") trapTab(e);
        }}
      >
        <div className="brand brand-row">
          <span className="brand-mark">
            <ScanSearch size={18} aria-hidden="true" /> QEOS
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
              <NavLink
                key={to}
                to={`/projects/${projectId}/${to}`}
                // Suites live under Test cases: the tab stays lit there too
                className={({ isActive }) => navClass({ isActive: isActive || (to === "cases" && /\/suites(\/|$)/.test(pathname)) })}
              >
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
