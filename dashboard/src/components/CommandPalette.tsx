import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { pushRecent } from "../lib/recentItems";
import { MIN_REMOTE, usePaletteGroups, type PaletteItem } from "./paletteSources";

const LISTBOX_ID = "palette-results";
const PLACEHOLDER = "Search cases, runs, tests…";

const isMac = () => typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent);

/** Typing goes to these, so "/" must not steal it. */
function typingIn(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el || !el.tagName) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

/** The first case-insensitive occurrence of `q` in `text`, wrapped in <mark>. */
export function Highlight({ text, q }: { text: string; q: string }) {
  const needle = q.trim().replace(/^#/, "");
  const at = needle ? text.toLowerCase().indexOf(needle.toLowerCase()) : -1;
  if (at < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, at)}
      <mark className="palette-mark">{text.slice(at, at + needle.length)}</mark>
      {text.slice(at + needle.length)}
    </>
  );
}

interface Props {
  /** The project on screen; null outside a project (only pages and projects are searched then). */
  projectId: number | null;
  /** Phones: the trigger is an icon button. */
  compact: boolean;
}

/** The top bar's search trigger and the command palette it opens (also on Ctrl K / ⌘K, and "/" outside a field). */
export default function CommandPalette({ projectId, compact }: Props) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  // Where focus was when it opened: Esc gives it back there (the trigger when nothing held it)
  const returnTo = useRef<HTMLElement | null>(null);
  const mac = useMemo(isMac, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Another handler took it, or an IME is mid-composition: not ours
      if (e.defaultPrevented || e.isComposing) return;
      // AltGr arrives as Ctrl+Alt on Windows: layouts that type "/" with it must still reach the palette
      const altGr = e.getModifierState?.("AltGraph") || (e.ctrlKey && e.altKey);
      const combo = e.key.toLowerCase() === "k" && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey;
      const slash = e.key === "/" && (altGr || (!e.ctrlKey && !e.metaKey)) && !typingIn(e.target);
      if (!combo && !slash) return;
      e.preventDefault();
      if (!open) {
        returnTo.current = document.activeElement as HTMLElement | null;
        setOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  function close(restoreFocus: boolean) {
    setOpen(false);
    if (!restoreFocus) return;
    const back = returnTo.current;
    // A deferred focus: the dialog unmounts first
    setTimeout(() => {
      const target = back && back !== document.body && back.isConnected ? back : triggerRef.current;
      target?.focus();
    }, 0);
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={compact ? "ghost palette-trigger compact" : "palette-trigger"}
        aria-label={compact ? "Search" : undefined}
        aria-haspopup="dialog"
        aria-keyshortcuts="Control+K Meta+K /"
        onClick={() => {
          returnTo.current = triggerRef.current;
          setOpen(true);
        }}
      >
        <Search size={compact ? 18 : 15} aria-hidden="true" />
        {!compact && (
          <>
            <span className="palette-trigger-text">{PLACEHOLDER}</span>
            <kbd aria-hidden="true">{mac ? "⌘K" : "Ctrl K"}</kbd>
          </>
        )}
      </button>
      {open && <Palette projectId={projectId} onClose={close} />}
    </>
  );
}

function Palette({ projectId, onClose }: { projectId: number | null; onClose: (restoreFocus: boolean) => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { groups, pending, userId } = usePaletteGroups(query, projectId);
  const options = useMemo(() => groups.flatMap((g) => g.items.map((item) => ({ item, domId: optionId(g.key, item.id) }))), [groups]);

  // The first result is active until the reader moves; a new query starts over
  const [chosen, setChosen] = useState<string | null>(null);
  useEffect(() => setChosen(null), [query]);
  const activeIndex = Math.max(0, chosen === null ? 0 : options.findIndex((o) => o.domId === chosen));
  const active = options[activeIndex];

  // A real modal: the palette lives in its own node on <body>; everything else there is inert and the page does not
  // scroll under it. Both are undone on close (before focus goes back, which an inert element would refuse).
  const host = useMemo(() => document.createElement("div"), []);
  useLayoutEffect(() => {
    document.body.appendChild(host);
    const others = Array.from(document.body.children).filter((el) => el !== host && !el.hasAttribute("inert"));
    others.forEach((el) => el.setAttribute("inert", ""));
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      others.forEach((el) => el.removeAttribute("inert"));
      document.body.style.overflow = overflow;
      host.remove();
    };
  }, [host]);

  useEffect(() => inputRef.current?.focus(), []);
  // Esc closes it wherever focus is, not only from the field
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      onClose(true);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  useEffect(() => {
    if (active) document.getElementById(active.domId)?.scrollIntoView?.({ block: "nearest" });
  }, [active]);

  function openItem(item: PaletteItem) {
    pushRecent(userId, item);
    onClose(false);
    navigate(item.href);
  }

  function move(to: number) {
    if (options.length === 0) return;
    const wrapped = (to + options.length) % options.length;
    setChosen(options[wrapped].domId);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case "ArrowDown": e.preventDefault(); move(activeIndex + 1); break;
      case "ArrowUp": e.preventDefault(); move(activeIndex - 1); break;
      case "Home": e.preventDefault(); move(0); break;
      case "End": e.preventDefault(); move(options.length - 1); break;
      case "Enter":
        e.preventDefault();
        if (active) openItem(active.item);
        break;
    }
  }

  const q = query.trim();
  const empty = q !== "" && !pending && groups.length === 0;
  const count = options.length;
  // Announced once the sources settle; never while an answer is still on its way
  const announcement = q === "" ? "" : pending ? null : empty ? `No matches for "${q}"` : `${count} ${count === 1 ? "result" : "results"}`;
  const [spoken, setSpoken] = useState("");
  useEffect(() => {
    if (announcement !== null) setSpoken(announcement);
  }, [announcement]);

  return createPortal(
    <>
      <div className="palette-backdrop" aria-hidden="true" onMouseDown={() => onClose(true)} />
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Search"
        onKeyDown={(e) => {
          // The input is the dialog's one stop: Tab stays on it
          if (e.key === "Tab") e.preventDefault();
        }}
      >
        <div className="palette-field">
          <Search size={16} aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-label="Search"
            aria-expanded={count > 0}
            aria-controls={LISTBOX_ID}
            aria-autocomplete="list"
            aria-activedescendant={active?.domId}
            autoComplete="off"
            spellCheck={false}
            placeholder={projectId !== null ? PLACEHOLDER : "Search pages and projects…"}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <kbd aria-hidden="true">Esc</kbd>
        </div>
        <div id={LISTBOX_ID} role="listbox" aria-label="Results" className="palette-results">
          {groups.map((g) => (
            <div key={g.key} role="group" aria-labelledby={`palette-group-${g.key}`} className="palette-group">
              <div id={`palette-group-${g.key}`} role="presentation" className="palette-group-label">{g.label}</div>
              {g.error ? (
                <div role="option" aria-disabled="true" aria-selected="false" id={`palette-notice-${g.key}`} className="palette-notice">
                  {g.error}
                </div>
              ) : (
                g.items.map((item) => {
                  const domId = optionId(g.key, item.id);
                  const isActive = active?.domId === domId;
                  return (
                    <div
                      key={item.id}
                      id={domId}
                      role="option"
                      aria-selected={isActive}
                      className={isActive ? "palette-option active" : "palette-option"}
                      onMouseMove={() => { if (!isActive) setChosen(domId); }}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => openItem(item)}
                    >
                      {item.kind === "case" && item.detail && <span className="palette-key">{item.detail}</span>}
                      <span className="palette-label"><Highlight text={item.label} q={g.key === "recent" ? "" : q} /></span>
                      {item.kind !== "case" && item.detail && <span className="palette-detail">{item.detail}</span>}
                    </div>
                  );
                })
              )}
            </div>
          ))}
        </div>
        {empty && <p className="palette-empty">No matches for "{q}"</p>}
        {pending && q.length >= MIN_REMOTE && <p className="palette-searching">Searching…</p>}
        <div role="status" className="sr-only">{spoken}</div>
      </div>
    </>,
    host,
  );
}

/** A DOM id for an option: the item id with anything outside [A-Za-z0-9-] spelled as _<code>, so ids stay unique. */
const optionId = (group: string, id: string) =>
  `palette-${group}-${id.replace(/[^A-Za-z0-9-]/g, (c) => `_${c.charCodeAt(0).toString(16)}`)}`;
