import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { SortState } from "../lib/sort";

interface Props<K extends string> {
  label: string;
  sortKey: K;
  /** null: the list is in the order the server sent it */
  sort: SortState<K> | null;
  onSort: (key: K) => void;
  className?: string;
}

/** A column header that sorts: the button sits inside the th, which carries aria-sort. */
export default function SortableTh<K extends string>({ label, sortKey, sort, onSort, className }: Props<K>) {
  const active = sort?.key === sortKey;
  const Icon = !sort || !active ? ChevronsUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th className={className} aria-sort={active ? (sort?.dir === "asc" ? "ascending" : "descending") : undefined}>
      <button type="button" className="sort-button" onClick={() => onSort(sortKey)}>
        {label}
        <Icon size={12} aria-hidden="true" className={active ? "sort-icon is-active" : "sort-icon"} />
      </button>
    </th>
  );
}
