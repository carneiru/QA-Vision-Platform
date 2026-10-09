import type { ReactNode } from "react";

/** Series that are not told apart by colour alone: each also has a fill texture and the legend repeats it. */
export interface LegendSeries {
  key: string;
  label: string;
  /** The SVG paint for a swatch: a colour var, or url(#pattern) */
  paint: string;
  /** A line series: the swatch is a stroke (dashed when `dash` is set) instead of a filled square */
  line?: { dash?: string; marker?: boolean };
}

export const PATTERN = {
  failed: "qeos-pat-failed",
  errored: "qeos-pat-errored",
  skipped: "qeos-pat-skipped",
  /** Cases with no linked test (Report: Coverage) */
  manual: "qeos-pat-manual",
} as const;

/** The textures for the stacked status bars: stripes for failed, dots for errored, lines for skipped, solid for passed.
 *  Rendered once per page; the chart and the legend swatches both point at these ids. Marks are drawn in the
 *  surface colour on the status colour, so both themes keep their contrast. */
export function ChartPatternDefs() {
  return (
    <svg width="0" height="0" aria-hidden="true" focusable="false" style={{ position: "absolute" }}>
      <defs>
        <pattern id={PATTERN.failed} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="var(--status-failed)" />
          <rect width="2" height="6" fill="var(--surface-1)" />
        </pattern>
        <pattern id={PATTERN.errored} width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="var(--status-errored)" />
          <circle cx="3" cy="3" r="1.2" fill="var(--surface-1)" />
        </pattern>
        <pattern id={PATTERN.skipped} width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="var(--status-skipped)" />
          <rect y="2.5" width="6" height="1" fill="var(--surface-1)" />
        </pattern>
        <pattern id={PATTERN.manual} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="var(--series-2)" />
          <rect width="2" height="6" fill="var(--surface-1)" />
        </pattern>
      </defs>
    </svg>
  );
}

function Swatch({ s }: { s: LegendSeries }) {
  if (s.line) {
    return (
      <svg width="22" height="12" aria-hidden="true" focusable="false">
        <line x1="1" y1="6" x2="21" y2="6" stroke={s.paint} strokeWidth="2" strokeDasharray={s.line.dash} />
        {s.line.marker !== false && <circle cx="11" cy="6" r="3" fill={s.paint} />}
      </svg>
    );
  }
  return (
    <svg width="14" height="14" aria-hidden="true" focusable="false">
      <rect width="14" height="14" rx="2" fill={s.paint} stroke="var(--border-strong)" strokeWidth="0.5" />
    </svg>
  );
}

/** A legend whose entries are toggle buttons: pressed means the series is shown. */
export function SeriesLegend({ series, hidden, onToggle, label }: {
  series: LegendSeries[];
  hidden: ReadonlySet<string>;
  onToggle: (key: string) => void;
  label: string;
}) {
  return (
    <ul className="series-legend" aria-label={label}>
      {series.map((s) => {
        const shown = !hidden.has(s.key);
        return (
          <li key={s.key}>
            <button type="button" className="legend-toggle" aria-pressed={shown} onClick={() => onToggle(s.key)} data-hidden={shown ? undefined : "true"}>
              <Swatch s={s} />
              <span>{s.label}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** A table that stands in for a chart, behind a native disclosure so it is one keystroke away and never hidden for good. */
export function DataTableDisclosure({ label = "Show data table", name, children }: { label?: string; name: string; children: ReactNode }) {
  return (
    <details className="chart-data">
      <summary>{label}<span className="sr-only"> for {name}</span></summary>
      <div className="chart-data-body" tabIndex={0} role="region" aria-label={`${name}: data`}>
        {children}
      </div>
    </details>
  );
}
