import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation, useMatch } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Building2, ClipboardList, FileText, FlaskConical, FolderKanban, GitBranch, LayoutDashboard, ListChecks, Menu,
  PanelLeftClose, PanelLeftOpen, ScanSearch, Settings, Shuffle, TrendingUp, X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { getProject, listMyOrganizations } from "../api/orgs";
import { useMediaQuery } from "../lib/useMediaQuery";
import Breadcrumb from "./Breadcrumb";
import UserMenu from "./UserMenu";

const PROJECT_VIEWS: { to: string; label: string; icon: LucideIcon }[] = [
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

/** Phones: the rail becomes a drawer behind the menu button (matches the CSS breakpoint). */
const DRAWER_QUERY = "(max-width: 640px)";
/** A new visitor gets the rail pinned open from this width up. */
const WIDE_QUERY = "(min-width: 1280px)";
const PIN_KEY = "qeos.rail.pinned";
/** The pointer must rest this long before the rail expands, so crossing it on the way elsewhere does not flash it open
 *  (until then, each item shows its label as a tooltip). */
const HOVER_INTENT_MS = 200;

const FOCUSABLE = "a[href], button:not(:disabled), select:not(:disabled), input:not(:disabled)";

function readPinned(): boolean {
  try {
    const stored = localStorage.getItem(PIN_KEY);
    if (stored === "1" || stored === "0") return stored === "1";
  } catch {
    // Storage blocked: fall back to the width default
  }
  return typeof window.matchMedia === "function" && window.matchMedia(WIDE_QUERY).matches;
}

function storePinned(pinned: boolean) {
  try {
    localStorage.setItem(PIN_KEY, pinned ? "1" : "0");
  } catch {
    // Storage blocked: the choice lasts until reload
  }
}

function RailLink({ to, label, icon: Icon, active }: { to: string; label: string; icon: LucideIcon; active: boolean }) {
  return (
    <li>
      <Link to={to} className={active ? "rail-link active" : "rail-link"} aria-current={active ? "page" : undefined}>
        <Icon size={18} aria-hidden="true" />
        <span className="rail-label">{label}</span>
      </Link>
    </li>
  );
}

/** Authenticated frame: a top bar (brand, breadcrumb with the project switcher, user menu), a left icon rail
 *  that expands over the content on hover or focus and can be pinned open, and the page. On phones the rail
 *  becomes a focus-managed drawer behind a menu button. */
export default function AppShell() {
  const { pathname } = useLocation();
  const projectMatch = useMatch("/projects/:projectId/*");
  const orgMatch = useMatch("/organizations/:orgId");
  const projectId = projectMatch ? Number(projectMatch.params.projectId) : null;

  const orgs = useQuery({ queryKey: ["orgs"], queryFn: listMyOrganizations });
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId!),
    enabled: projectId !== null,
  });

  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(readPinned);
  const [hovered, setHovered] = useState(false);
  const [focusInside, setFocusInside] = useState(false);
  const hoverTimer = useRef<ReturnType<typeof setTimeout>>();
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(false);
  const drawerLayout = useMediaQuery(DRAWER_QUERY);
  const expanded = !drawerLayout && (pinned || hovered || focusInside);

  useEffect(() => () => clearTimeout(hoverTimer.current), []);

  function togglePin() {
    const next = !pinned;
    setPinned(next);
    storePinned(next);
  }

  // Focus goes back to the menu button only when the reader closes the drawer. A followed link closes it too,
  // but then the new page's heading takes focus (routeFocus): the button must not take it back.
  const focusMenuOnClose = useRef(true);
  const closeForNavigation = () => {
    focusMenuOnClose.current = false;
    setOpen(false);
  };
  useEffect(() => closeForNavigation(), [pathname]);
  // The layout widened past the drawer breakpoint while it was open: it is a plain rail again
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

  // The organization the rail and the user menu open: the current project's, the one on screen, else the first
  const orgId = project.data?.organization_id ?? (orgMatch ? Number(orgMatch.params.orgId) : orgs.data?.[0]?.id);
  const inView = (to: string) => {
    const base = `/projects/${projectId}/${to}`;
    const under = (p: string) => pathname === p || pathname.startsWith(`${p}/`);
    // Suites live under Test cases: the item stays lit there too
    return under(base) || (to === "cases" && under(`/projects/${projectId}/suites`));
  };

  const railClass = ["rail", expanded && "expanded", expanded && !pinned && "overlay", open && "open"].filter(Boolean).join(" ");

  return (
    <div className={pinned && !drawerLayout ? "shell rail-pinned" : "shell"}>
      <header className="topbar">
        <button
          ref={menuButton}
          className="ghost menu-button"
          aria-label="Open navigation"
          aria-expanded={open}
          aria-controls="sidebar"
          onClick={() => setOpen(true)}
        >
          <Menu size={20} aria-hidden="true" />
        </button>
        <Link to="/" className="brand" aria-label="QEOS, all projects">
          <ScanSearch size={18} aria-hidden="true" /> QEOS
        </Link>
        <Breadcrumb />
        <span className="topbar-spacer" />
        <UserMenu orgId={orgId} />
      </header>

      <div
        id="sidebar"
        ref={sidebar}
        className={railClass}
        aria-label={open && drawerLayout ? "Navigation" : undefined}
        role={open && drawerLayout ? "dialog" : undefined}
        aria-modal={open && drawerLayout ? true : undefined}
        onKeyDown={(e) => {
          if (open && drawerLayout && e.key === "Tab") trapTab(e);
        }}
        onMouseEnter={() => {
          clearTimeout(hoverTimer.current);
          hoverTimer.current = setTimeout(() => setHovered(true), HOVER_INTENT_MS);
        }}
        onMouseLeave={() => {
          clearTimeout(hoverTimer.current);
          setHovered(false);
        }}
        onFocus={() => setFocusInside(true)}
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setFocusInside(false);
        }}
      >
        {open && (
          <div className="drawer-head">
            <span className="brand">
              <ScanSearch size={18} aria-hidden="true" /> QEOS
            </span>
            <button className="ghost" aria-label="Close navigation" onClick={() => setOpen(false)}>
              <X size={18} aria-hidden="true" />
            </button>
          </div>
        )}

        <nav className="rail-nav" aria-label="Main">
          {projectId !== null && (
            <ul className="rail-list">
              {PROJECT_VIEWS.map(({ to, label, icon }) => (
                <RailLink key={to} to={`/projects/${projectId}/${to}`} label={label} icon={icon} active={inView(to)} />
              ))}
            </ul>
          )}
          <ul className="rail-list rail-workspace">
            <RailLink to="/" label="All projects" icon={FolderKanban} active={pathname === "/"} />
            {orgId !== undefined && (
              <RailLink to={`/organizations/${orgId}`} label="Organization" icon={Building2} active={pathname.startsWith("/organizations/")} />
            )}
          </ul>
        </nav>

        {!drawerLayout && (
          <button
            type="button"
            className="ghost rail-pin"
            aria-pressed={pinned}
            aria-label={pinned ? "Collapse sidebar" : "Expand sidebar"}
            onClick={togglePin}
          >
            {pinned ? <PanelLeftClose size={18} aria-hidden="true" /> : <PanelLeftOpen size={18} aria-hidden="true" />}
            <span className="rail-label" aria-hidden="true">{pinned ? "Collapse sidebar" : "Expand sidebar"}</span>
          </button>
        )}
      </div>
      <div className={open ? "backdrop open" : "backdrop"} onClick={() => setOpen(false)} aria-hidden="true" />

      <div className="shell-main">
        <main id="main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
