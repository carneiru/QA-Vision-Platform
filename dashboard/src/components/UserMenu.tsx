import { KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Building2, LogOut, ShieldCheck } from "lucide-react";
import { getMe, logout } from "../api/auth";

/** "pedro.carneiro@x.com" -> "PC", "ana@x.com" -> "AN" */
export function initials(email: string): string {
  const local = email.split("@")[0] ?? "";
  const parts = local.split(/[._+-]+/).filter(Boolean);
  const letters = parts.length >= 2 ? parts[0][0] + parts[1][0] : local.slice(0, 2);
  return letters.toUpperCase() || "?";
}

interface Props {
  /** The organization to open from the menu (the current project's, else the first); none hides the item */
  orgId?: number;
}

/** The avatar in the top bar and its menu: who is signed in, Security, Organization and Sign out.
 *  Menu-button pattern: arrows move between items, Escape closes and returns focus to the avatar. */
export default function UserMenu({ orgId }: Props) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const me = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: 5 * 60_000 });
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const ids = useId();

  const email = me.data?.email;
  const items = () => Array.from(menu.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);

  function close(returnFocus: boolean) {
    setOpen(false);
    if (returnFocus) button.current?.focus();
  }

  // Opening puts focus on the first item; a followed link closes the menu
  useEffect(() => {
    if (open) items()[0]?.focus();
  }, [open]);
  useEffect(() => setOpen(false), [pathname]);

  // A press outside closes it, leaving focus where the press put it
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent | MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  function onMenuKey(e: KeyboardEvent<HTMLDivElement>) {
    const list = items();
    const at = list.indexOf(document.activeElement as HTMLElement);
    const go = (i: number) => {
      e.preventDefault();
      list[(i + list.length) % list.length]?.focus();
    };
    if (e.key === "ArrowDown") go(at + 1);
    else if (e.key === "ArrowUp") go(at - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(list.length - 1);
    else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close(true);
    } else if (e.key === "Tab") setOpen(false);
  }

  async function onSignOut() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="user-menu" ref={box}>
      <button
        ref={button}
        type="button"
        className="avatar-button"
        aria-label={email ? `Account menu for ${email}` : "Account menu"}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? `${ids}-menu` : undefined}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" && !open) {
            e.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span aria-hidden="true">{email ? initials(email) : ""}</span>
      </button>
      {open && (
        <div className="user-menu-popup">
          {email && <p className="user-menu-email">{email}</p>}
          <div ref={menu} id={`${ids}-menu`} role="menu" aria-label="Account" onKeyDown={onMenuKey}>
            <Link role="menuitem" tabIndex={-1} to="/account/security" className="menu-item">
              <ShieldCheck size={16} aria-hidden="true" /> Security
            </Link>
            {orgId !== undefined && (
              <Link role="menuitem" tabIndex={-1} to={`/organizations/${orgId}`} className="menu-item">
                <Building2 size={16} aria-hidden="true" /> Organization
              </Link>
            )}
            <div role="separator" className="menu-separator" />
            <button role="menuitem" tabIndex={-1} type="button" className="menu-item" onClick={onSignOut}>
              <LogOut size={16} aria-hidden="true" /> Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
