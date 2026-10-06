import { useEffect, useId, useMemo, useRef, useState } from "react";
import { norm } from "./FilterSelect";
import FolderTree, { FolderCount, FolderNode, buildTree, countFolders, displayPath, filterTree } from "./FolderTree";

interface Props {
  label?: string;
  folders: FolderCount[];
  total?: number;
  value: string;
  onChange: (path: string) => void;
}

/** The first folder, top to bottom, whose own name matches the search (ancestors that only lead to a match don't count). */
function firstMatch(tree: FolderNode[], q: string): string | null {
  for (const n of tree) {
    if (norm(n.name).includes(q)) return n.path;
    const inner = firstMatch(n.children, q);
    if (inner) return inner;
  }
  return null;
}

/** The folder filter: looks like the other filters; opens a popup with a search box and the folder tree. */
export default function FolderSelect({ label = "Folder", folders, total, value, onChange }: Props) {
  const uid = useId();
  const labelId = `${uid}-label`;
  const triggerId = `${uid}-trigger`;
  const popupId = `${uid}-popup`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const fieldRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const tree = useMemo(() => buildTree(folders), [folders]);
  const all = useMemo(() => countFolders(tree), [tree]);
  const shown = useMemo(() => countFolders(filterTree(tree, query)), [tree, query]);
  const shownText = value ? displayPath(folders, value) : "All folders";

  const reset = () => { setOpen(false); setQuery(""); };
  const close = () => { reset(); triggerRef.current?.focus(); };
  const pick = (path: string) => { onChange(path); close(); };

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (fieldRef.current && !fieldRef.current.contains(e.target as Node)) { setOpen(false); setQuery(""); }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const onPopupKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "Tab") { e.preventDefault(); close(); }
  };

  const onSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault(); // inside the Cases form this would submit it
      const q = norm(query.trim());
      const first = q ? firstMatch(filterTree(tree, query), q) : null;
      if (first) pick(first);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      fieldRef.current?.querySelector<HTMLElement>('[role="treeitem"]')?.focus();
    }
  };

  return (
    <div className="combo-field" ref={fieldRef}>
      <span id={labelId} className="combo-label">{label}</span>
      <div className="combo-control">
        <button
          type="button"
          ref={triggerRef}
          id={triggerId}
          className="combo-trigger"
          aria-haspopup="dialog"
          aria-controls={open ? popupId : undefined}
          aria-expanded={open}
          aria-labelledby={`${labelId} ${triggerId}`}
          onClick={() => (open ? close() : setOpen(true))}
        >
          <span className="combo-value">{shownText}</span>
        </button>
        {value && (
          <button type="button" className="combo-clear" aria-label={`Clear ${label}`} onClick={() => { onChange(""); triggerRef.current?.focus(); }}>×</button>
        )}
      </div>
      {open && (
        <div className="combo-popup folder-popup" id={popupId} role="dialog" aria-labelledby={labelId} onKeyDown={onPopupKeyDown}>
          <input
            ref={searchRef}
            type="search"
            aria-label="Search folders"
            autoComplete="off"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onSearchKeyDown}
          />
          <div className="combo-count" aria-live="polite">{shown} of {all}</div>
          <div className="combo-body">
            <FolderTree
              folders={folders}
              total={total}
              selected={value}
              onSelect={pick}
              filter={query}
              toggle={false}
              onLeaveTop={() => searchRef.current?.focus()}
            />
          </div>
        </div>
      )}
    </div>
  );
}
