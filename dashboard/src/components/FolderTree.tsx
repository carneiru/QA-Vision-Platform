import { KeyboardEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { norm } from "./FilterSelect";

export interface FolderCount { path: string; count: number }
export interface FolderNode { path: string; name: string; count: number; children: FolderNode[] }

export function buildTree(folders: FolderCount[]): FolderNode[] {
  const nodes = new Map<string, FolderNode>();
  for (const f of folders) {
    nodes.set(f.path, { path: f.path, name: f.path.split("/").pop() ?? f.path, count: f.count, children: [] });
  }
  let roots: FolderNode[] = [];
  for (const node of nodes.values()) {
    const cut = node.path.lastIndexOf("/");
    const parent = cut > 0 ? nodes.get(node.path.slice(0, cut)) : undefined;
    (parent ? parent.children : roots).push(node);
  }
  const sort = (list: FolderNode[]) => {
    list.sort((a, b) => a.name.localeCompare(b.name));
    list.forEach((n) => sort(n.children));
  };
  sort(roots);
  while (roots.length === 1 && roots[0].children.length === 1) roots = roots[0].children;
  return roots;
}

/** Keeps folders whose own name matches, plus the ancestors that lead to them. */
export function filterTree(tree: FolderNode[], query: string): FolderNode[] {
  const q = norm(query.trim());
  if (!q) return tree;
  const walk = (list: FolderNode[]): FolderNode[] =>
    list.flatMap((n) => {
      const children = walk(n.children);
      return children.length > 0 || norm(n.name).includes(q) ? [{ ...n, children }] : [];
    });
  return walk(tree);
}

export function countFolders(tree: FolderNode[]): number {
  return tree.reduce((n, f) => n + 1 + countFolders(f.children), 0);
}

/** A folder's path as shown to people, starting at the collapsed root: `features / hotels`. */
export function displayPath(folders: FolderCount[], path: string): string {
  if (!path) return "";
  const root = buildTree(folders).find((r) => path === r.path || path.startsWith(`${r.path}/`));
  const rest = root ? path.slice(root.path.length).split("/").filter(Boolean) : path.split("/");
  return [...(root ? [root.name] : []), ...rest].join(" / ");
}

/** Wraps the part of a name that matches the search in <mark>, ignoring case and accents. */
function highlight(name: string, query: string): ReactNode {
  const q = norm(query.trim());
  if (!q) return name;
  const chars = Array.from(name);
  let flat = "";
  const owner: number[] = [];
  chars.forEach((c, i) => { const n = norm(c); flat += n; for (let k = 0; k < n.length; k++) owner.push(i); });
  const at = flat.indexOf(q);
  if (at < 0) return name;
  const from = owner[at];
  const to = owner[at + q.length - 1] + 1;
  return <>{chars.slice(0, from).join("")}<mark>{chars.slice(from, to).join("")}</mark>{chars.slice(to).join("")}</>;
}

interface Row { path: string; level: number; parent: string | null; hasChildren: boolean }

const ancestorsOf = (path: string): string[] => {
  const parts = path.split("/").filter(Boolean);
  return parts.map((_, i) => parts.slice(0, i + 1).join("/"));
};

export default function FolderTree({ folders, total, selected, onSelect, filter = "", toggle: canClear = true, onLeaveTop }: {
  folders: FolderCount[];
  total: number;
  selected: string;
  onSelect: (path: string) => void;
  /** Show only folders whose name contains this text, with their ancestors, all expanded. */
  filter?: string;
  /** Clicking the selected folder clears it (default); a dropdown turns this off. */
  toggle?: boolean;
  /** Called when ArrowUp is pressed on the first item. */
  onLeaveTop?: () => void;
}) {
  const searching = filter.trim() !== "";
  const full = useMemo(() => buildTree(folders), [folders]);
  const tree = useMemo(() => filterTree(full, filter), [full, filter]);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(["", ...ancestorsOf(selected).slice(0, -1)]));
  const [focused, setFocused] = useState<string | null>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    setFocused(null);
    if (!selected) return;
    setExpanded((prev) => {
      const next = new Set(prev);
      ancestorsOf(selected).slice(0, -1).forEach((p) => next.add(p));
      return next.size === prev.size ? prev : next;
    });
  }, [selected]);

  const isOpenRow = (p: string) => searching || expanded.has(p);

  const rows = useMemo(() => {
    const out: Row[] = [{ path: "", level: 1, parent: null, hasChildren: tree.length > 0 }];
    const walk = (list: FolderNode[], level: number, parent: string) => {
      for (const n of list) {
        out.push({ path: n.path, level, parent, hasChildren: n.children.length > 0 });
        if (n.children.length && (searching || expanded.has(n.path))) walk(n.children, level + 1, n.path);
      }
    };
    if (searching || expanded.has("")) walk(tree, 2, "");
    return out;
  }, [tree, expanded, searching]);

  const visible = (p: string | null) => p !== null && rows.some((r) => r.path === p);
  const tabbable = visible(focused) ? focused : visible(selected) ? selected : "";

  const toggle = (path: string, open?: boolean) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      const want = open ?? !next.has(path);
      if (want) next.add(path); else next.delete(path);
      return next;
    });

  const choose = (path: string) => onSelect(path === "" || (canClear && path === selected) ? "" : path);

  const focusPath = (path: string) => {
    setFocused(path);
    listRef.current?.querySelectorAll<HTMLElement>('[role="treeitem"]').forEach((el) => {
      if (el.dataset.path === path) el.focus();
    });
  };

  const onKeyDown = (e: KeyboardEvent<HTMLUListElement>) => {
    const item = (e.target as HTMLElement).closest<HTMLElement>('[role="treeitem"]');
    if (!item) return;
    const path = item.dataset.path ?? "";
    const idx = rows.findIndex((r) => r.path === path);
    if (idx < 0) return;
    const row = rows[idx];
    const isOpen = isOpenRow(path);
    switch (e.key) {
      case "ArrowDown": e.preventDefault(); if (rows[idx + 1]) focusPath(rows[idx + 1].path); break;
      case "ArrowUp": e.preventDefault(); if (rows[idx - 1]) focusPath(rows[idx - 1].path); else onLeaveTop?.(); break;
      case "ArrowRight":
        e.preventDefault();
        if (!row.hasChildren) break;
        if (!isOpen) toggle(path, true); else if (rows[idx + 1]) focusPath(rows[idx + 1].path);
        break;
      case "ArrowLeft":
        e.preventDefault();
        if (row.hasChildren && isOpen) toggle(path, false);
        else if (row.parent !== null) focusPath(row.parent);
        break;
      case "Home": e.preventDefault(); focusPath(rows[0].path); break;
      case "End": e.preventDefault(); focusPath(rows[rows.length - 1].path); break;
      case "Enter":
      case " ": e.preventDefault(); choose(path); break;
      default: break;
    }
  };

  const renderItem = (path: string, name: string, count: number, level: number, children: FolderNode[]) => {
    const hasChildren = children.length > 0;
    const isOpen = isOpenRow(path);
    return (
      <li
        key={path || "all"}
        role="treeitem"
        data-path={path}
        aria-level={level}
        aria-label={`${name} ${count}`}
        aria-selected={selected === path}
        aria-expanded={hasChildren ? isOpen : undefined}
        tabIndex={tabbable === path ? 0 : -1}
        onFocus={(e) => { if (e.target === e.currentTarget) setFocused(path); }}
        onClick={(e) => { e.stopPropagation(); choose(path); }}
      >
        <div className="folder-row" style={{ paddingLeft: `calc(var(--space-2) + ${level - 1} * var(--space-4))` }}>
          {hasChildren ? (
            <span
              className="folder-chevron"
              aria-hidden="true"
              data-open={isOpen}
              onClick={(e) => { e.stopPropagation(); toggle(path); }}
            />
          ) : <span className="folder-chevron-space" aria-hidden="true" />}
          <span className="folder-name">{path ? highlight(name, filter) : name}</span>
          <span className="folder-count">{count}</span>
        </div>
        {hasChildren && isOpen && (
          <ul role="group">{children.map((c) => renderItem(c.path, c.name, c.count, level + 1, c.children))}</ul>
        )}
      </li>
    );
  };

  if (searching && tree.length === 0) return <div className="combo-empty">No matches</div>;
  return (
    <ul className="folder-tree" role="tree" aria-label="Folders" ref={listRef} onKeyDown={onKeyDown}>
      {renderItem("", "All cases", total, 1, tree)}
    </ul>
  );
}
