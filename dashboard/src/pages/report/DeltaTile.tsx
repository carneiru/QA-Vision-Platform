import { ArrowDown, ArrowUp, CircleAlert, CircleCheck, CircleDot, Minus } from "lucide-react";
import type { Delta } from "../../lib/reportDelta";

const ARROW = { up: ArrowUp, down: ArrowDown, flat: Minus } as const;
const TONE_ICON = { neutral: CircleDot, good: CircleCheck, bad: CircleAlert } as const;

/** A KPI tile with its change against the previous period (DESIGN.md: KPI Tiles, Delta Tiles). The change is an
 *  icon plus words, and "better" or "worse" says the verdict: never colour alone. The group's name is the sentence. */
export default function DeltaTile({ title, value, delta, noPrevious }: {
  title: string;
  value: string;
  delta: Delta | null;
  noPrevious: boolean;
}) {
  const tone = delta?.verdict === "better" ? "good" : delta?.verdict === "worse" ? "bad" : "neutral";
  const ToneIcon = TONE_ICON[tone];
  const Arrow = delta ? ARROW[delta.direction] : null;
  const spoken = noPrevious
    ? "no data in the previous period"
    : delta ? `${delta.spoken}${delta.verdict ? `, ${delta.verdict}` : ""}` : "";
  return (
    <div role="group" aria-label={`${title} ${value}${spoken ? `, ${spoken}` : ""}`} className={`kpi kpi-${tone}`}>
      <div className="kpi-body" aria-hidden="true">
        <span className="kpi-title"><span className="kpi-tone"><ToneIcon size={14} aria-hidden="true" /></span>{title}</span>
        <span className="kpi-value">{value}</span>
        {noPrevious ? (
          <span className="kpi-sub">No data in the previous period</span>
        ) : delta && Arrow ? (
          <span className={`kpi-sub delta-${delta.verdict ?? "neutral"}`}>
            <Arrow size={13} aria-hidden="true" />
            <span>{delta.text}</span>
            {delta.verdict && <strong className="delta-verdict">· {delta.verdict}</strong>}
          </span>
        ) : null}
      </div>
    </div>
  );
}
