import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { formatPassRate, getFlaky, getLatestKeys, getTrends } from "../api/analytics";
import { MAX_SEARCH_KEYS, listCases, searchCases } from "../api/cases";
import { FLAKY_DEFAULTS } from "../lib/flaky";
import { SkeletonStatus } from "./Skeleton";

type Tone = "neutral" | "good" | "bad";

interface TileProps {
  title: string;
  /** What the tile says in one sentence, for assistive tech (the visible parts are terse). */
  label: string;
  value: string;
  sub?: ReactNode;
  tone: Tone;
  /** A tile that leads somewhere is a link (never while it shows an error). */
  to?: string;
  query: { isPending: boolean; isError: boolean; refetch: () => unknown };
}

function Tile({ title, label, value, sub, tone, to, query }: TileProps) {
  if (query.isPending) {
    return (
      <SkeletonStatus label={`Loading ${title.toLowerCase()}…`} className="kpi kpi-neutral">
        <span className="kpi-title" aria-hidden="true">{title}</span>
        <span className="skeleton kpi-skeleton" aria-hidden="true" />
      </SkeletonStatus>
    );
  }
  if (query.isError) {
    return (
      <div role="group" aria-label={`${title} unavailable`} className="kpi kpi-neutral">
        <span className="kpi-title" aria-hidden="true">{title}</span>
        <span className="kpi-value" aria-hidden="true">—</span>
        <button type="button" className="kpi-retry" aria-label={`Retry ${title.toLowerCase()}`} onClick={() => query.refetch()}>
          Retry
        </button>
      </div>
    );
  }
  const body = (
    <>
      <span className="kpi-title">{title}</span>
      <span className="kpi-value">{value}</span>
      {sub}
    </>
  );
  return to ? (
    <Link to={to} className={`kpi kpi-${tone}`} aria-label={label}>{body}</Link>
  ) : (
    <div role="group" aria-label={label} className={`kpi kpi-${tone}`}>
      <div className="kpi-body" aria-hidden="true">{body}</div>
    </div>
  );
}

const count = (n: number) => n.toLocaleString();

/** The change in pass rate, in points to one decimal: the word always says the direction, never the colour alone. */
function trend(now: number, before: number) {
  const points = Math.round((now - before) * 1000) / 10;
  if (points === 0) return { tone: "good" as const, cls: "flat", Icon: Minus, short: "flat", spoken: "flat" };
  const dir = points > 0 ? "up" : "down";
  const size = Math.abs(points).toFixed(1);
  return {
    tone: points > 0 ? ("good" as const) : ("bad" as const), cls: dir, Icon: points > 0 ? ArrowUp : ArrowDown,
    short: `${dir} ${size} pts`, spoken: `${dir} ${size} points`,
  };
}

/** Four tiles over the Cases list: how many cases, the week's pass rate against the last, how many linked cases
 *  failed last time (a link that applies the Failing chip) and how many tests are flaky (a link to Flaky).
 *  Each loads, fails and retries on its own. */
export default function CasesKpis({ projectId }: { projectId: number }) {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

  // Same key and request as the page's folder total, so the two share one answer
  const total = useQuery({
    queryKey: ["cases-total", projectId],
    queryFn: async () => (await listCases(projectId, { limit: 1, offset: 0 })).total,
  });
  const imported = useQuery({
    queryKey: ["cases-total", projectId, "imported"],
    queryFn: async () => (await listCases(projectId, { origin: "imported", limit: 1, offset: 0 })).total,
  });
  // Overview's "Pass rate this week" query: the same key, so a visit to either fills both
  const weeks = useQuery({
    queryKey: ["trends", projectId, "overview-weeks", tz],
    queryFn: () => getTrends(projectId, { days: 14, tz, bucket: "week" }),
  });
  // The "Failing" chip's join, counted: tests whose latest result failed, then the cases linked to them
  const failing = useQuery({
    queryKey: ["cases-kpi", projectId, "failing"],
    queryFn: async () => {
      const { keys } = await getLatestKeys(projectId, "failed");
      if (keys.length === 0) return 0;
      if (keys.length > MAX_SEARCH_KEYS) return null;
      return (await searchCases(projectId, { test_keys: keys, keys_mode: "include", limit: 1, offset: 0 })).total;
    },
  });
  const flaky = useQuery({
    queryKey: ["flaky", projectId, "cases-kpi"],
    queryFn: () => getFlaky(projectId, { ...FLAKY_DEFAULTS, includeMuted: true }),
  });

  // Cases
  const casesValue = total.data !== undefined ? count(total.data) : "";
  const importedText = imported.data !== undefined ? `${count(imported.data)} imported` : null;

  // Pass rate
  const buckets = weeks.data?.days ?? [];
  const thisRate = buckets[buckets.length - 1]?.pass_rate ?? null;
  const lastRate = buckets.length > 1 ? buckets[buckets.length - 2].pass_rate : null;
  const change = thisRate !== null && lastRate !== null ? trend(thisRate, lastRate) : null;
  const rateValue = formatPassRate(thisRate);
  const rateLabel = thisRate === null
    ? "Pass rate: no runs this week"
    : `Pass rate ${rateValue}, ${change ? `${change.spoken} versus last week` : "no runs the week before"}`;
  const rateSub = thisRate === null ? (
    <span className="kpi-sub">no runs this week</span>
  ) : change ? (
    <span className={`kpi-sub ${change.cls}`}><change.Icon size={13} aria-hidden="true" /> {change.short} vs last week</span>
  ) : (
    <span className="kpi-sub">no runs the week before</span>
  );

  // Failing
  const failingCount = failing.data;
  const failingLabel = failingCount === null || failingCount === undefined
    ? "Failing: too many failing tests to count"
    : `Failing ${count(failingCount)} linked ${failingCount === 1 ? "case" : "cases"} whose latest result failed`;

  // Flaky
  const flakyCount = flaky.data?.filter((r) => !r.muted).length ?? 0;
  const quarantined = flaky.data?.filter((r) => r.muted).length ?? 0;

  return (
    <ul className="kpi-tiles" aria-label="Case summary">
      <li>
        <Tile
          title="Cases" query={total} tone="neutral" value={casesValue}
          label={`Cases ${casesValue}${importedText ? `, ${importedText}` : ""}`}
          sub={importedText && <span className="kpi-sub">{importedText}</span>}
        />
      </li>
      <li>
        <Tile title="Pass rate" query={weeks} tone={change?.tone ?? "neutral"} value={rateValue} label={rateLabel} sub={rateSub} />
      </li>
      <li>
        <Tile
          title="Failing" query={failing} tone={failingCount ? "bad" : "neutral"} label={failingLabel}
          value={failingCount === null || failingCount === undefined ? "—" : count(failingCount)}
          sub={<span className="kpi-sub">{failingCount === null ? "too many to count" : "latest result failed"}</span>}
          to={`/projects/${projectId}/cases?result=failed`}
        />
      </li>
      <li>
        <Tile
          title="Flaky" query={flaky} tone="neutral" value={count(flakyCount)}
          label={`Flaky ${count(flakyCount)} ${flakyCount === 1 ? "test" : "tests"} in the last ${FLAKY_DEFAULTS.windowDays} days, ${count(quarantined)} quarantined`}
          sub={<span className="kpi-sub">{count(quarantined)} quarantined</span>}
          to={`/projects/${projectId}/flaky`}
        />
      </li>
    </ul>
  );
}
