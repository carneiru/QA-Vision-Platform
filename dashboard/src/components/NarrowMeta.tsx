import type { ReactNode } from "react";

export interface NarrowMetaItem {
  label: string;
  value: ReactNode;
}

/** The columns a table drops on phones (`hide-narrow`), as a muted second line in the row's
 *  primary cell. It is display:none on wide screens, where the columns are shown, so the
 *  values are never read twice. Items with no value are skipped. */
export default function NarrowMeta({ items }: { items: NarrowMetaItem[] }) {
  const shown = items.filter((i) => i.value !== null && i.value !== undefined && i.value !== "" && i.value !== false);
  if (shown.length === 0) return null;
  return (
    <span className="cell-meta narrow-meta">
      {shown.map((i) => (
        <span key={i.label}>
          <span className="cell-meta-label">{i.label}</span> {i.value}
        </span>
      ))}
    </span>
  );
}
