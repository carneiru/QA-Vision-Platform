/** Which way is good for a metric: pass rate "up", failures and durations "down", runs "neither". */
export type Better = "up" | "down" | "neither";

/** A change against the previous period, in words: never an arrow or a colour alone (DESIGN.md, KPI Tiles). */
export interface Delta {
  direction: "up" | "down" | "flat";
  /** Visible: "up 1.2 pts vs previous 30 days" */
  text: string;
  /** For the tile's accessible name: "up 1.2 points versus the previous 30 days" */
  spoken: string;
  verdict: "better" | "worse" | null;
}

function verdict(direction: Delta["direction"], better: Better): Delta["verdict"] {
  if (direction === "flat" || better === "neither") return null;
  return direction === better ? "better" : "worse";
}

function flat(days: number): Delta {
  return {
    direction: "flat",
    text: `no change vs previous ${days} days`,
    spoken: `no change versus the previous ${days} days`,
    verdict: null,
  };
}

/** A rate (0..1) as percentage points to one decimal. */
export function pointsDelta(
  current: number | null,
  previous: number | null,
  days: number,
  better: Better
): Delta | null {
  if (current === null || previous === null) return null;
  const points = Math.round((current - previous) * 1000) / 10;
  if (points === 0) return flat(days);
  const direction = points > 0 ? "up" : "down";
  const size = Math.abs(points).toFixed(1);
  return {
    direction,
    text: `${direction} ${size} pts vs previous ${days} days`,
    spoken: `${direction} ${size} points versus the previous ${days} days`,
    verdict: verdict(direction, better),
  };
}

/** A count or a duration as a whole percentage of the previous value. */
export function relativeDelta(
  current: number | null,
  previous: number | null,
  days: number,
  better: Better
): Delta | null {
  if (current === null || previous === null) return null;
  if (previous === 0) {
    if (current === 0) return flat(days);
    return {
      direction: "up",
      text: `up from 0 vs previous ${days} days`,
      spoken: `up from 0 versus the previous ${days} days`,
      verdict: verdict("up", better),
    };
  }
  const percent = Math.round(((current - previous) / previous) * 100);
  if (percent === 0) return flat(days);
  const direction = percent > 0 ? "up" : "down";
  const size = Math.abs(percent);
  return {
    direction,
    text: `${direction} ${size}% vs previous ${days} days`,
    spoken: `${direction} ${size} percent versus the previous ${days} days`,
    verdict: verdict(direction, better),
  };
}
