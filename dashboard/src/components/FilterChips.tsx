import { useEffect, useRef } from "react";
import { Check, Plus, X } from "lucide-react";

/** A one-press filter: sets `key` to `value` in the URL. Chips sharing a key are one choice. */
export interface QuickChip {
  key: string;
  value: string;
  label: string;
}

/** A filter in force, as the reader names it ("Label", "flights"). */
export interface AppliedFilter {
  key: string;
  name: string;
  value: string;
}

interface Props {
  quick?: readonly QuickChip[];
  /** The applied URL values by key ("" when unset) */
  values: Readonly<Record<string, string>>;
  /** Every applied filter; those a pressed quick chip already shows are left out */
  applied: readonly AppliedFilter[];
  /** A patch of URL values; "" removes the key */
  onChange: (patch: Record<string, string>) => void;
  onClearAll: () => void;
  /** Opens the page's full filter form; no "+ Filter" without one */
  onAddFilter?: () => void;
}

/** The chips row between the filter form and the table: quick filters as toggle buttons, then every other
 *  filter in force as a removable chip, "+ Filter" and "Clear all". It only reads and patches URL values.
 *  The row is always mounted (empty when there is nothing to show) so focus can return to it. */
export default function FilterChips({ quick = [], values, applied, onChange, onClearAll, onAddFilter }: Props) {
  const isOn = (c: QuickChip) => (values[c.key] ?? "") === c.value;
  const shownByQuick = (f: AppliedFilter) => quick.some((c) => c.key === f.key && isOn(c));
  const removable = applied.filter((f) => !shownByQuick(f));
  const anyApplied = removable.length > 0 || quick.some(isOn);

  // A removed chip (or Clear all) unmounts the focused button: once the URL has caught up, focus goes to the chip
  // that took its place, else the one before it, else the row itself. Never the page body.
  const groupRef = useRef<HTMLDivElement>(null);
  const pending = useRef<{ key: string | null; index: number } | null>(null);
  const removedKeys = removable.map((f) => f.key).join("|");
  useEffect(() => {
    const want = pending.current;
    const group = groupRef.current;
    if (!want || !group) return;
    if (want.key !== null && removedKeys.split("|").includes(want.key)) return; // not applied yet
    if (want.key === null && anyApplied) return;
    pending.current = null;
    const chips = [...group.querySelectorAll<HTMLElement>("button.fchip, button.fchip-remove")];
    const target = want.key === null ? null : chips[want.index] ?? chips[want.index - 1];
    (target ?? group).focus();
  }, [removedKeys, anyApplied]);
  const chipIndex = (el: HTMLElement) =>
    [...(groupRef.current?.querySelectorAll("button.fchip, button.fchip-remove") ?? [])].indexOf(el);

  return (
    <div ref={groupRef} className="filter-chips" role="group" aria-label="Quick filters" tabIndex={-1}>
      {quick.map((c) => {
        const on = isOn(c);
        return (
          <button
            key={`${c.key}=${c.value}`}
            type="button"
            className={on ? "fchip is-on" : "fchip"}
            aria-pressed={on}
            onClick={() => onChange({ [c.key]: on ? "" : c.value })}
          >
            {on && <Check size={12} aria-hidden="true" />}
            {c.label}
          </button>
        );
      })}
      {removable.map((f) => (
        <span key={f.key} className="fchip fchip-applied">
          <span>{`${f.name}: ${f.value}`}</span>
          <button type="button" className="fchip-remove" aria-label={`Remove filter ${f.name}: ${f.value}`} onClick={(e) => {
              pending.current = { key: f.key, index: chipIndex(e.currentTarget) };
              onChange({ [f.key]: "" });
            }}>
            <X size={12} aria-hidden="true" />
          </button>
        </span>
      ))}
      {onAddFilter && (
        <button type="button" className="fchip fchip-add" aria-label="+ Filter" onClick={onAddFilter}>
          <Plus size={12} aria-hidden="true" />
          Filter
        </button>
      )}
      {anyApplied && (
        <button type="button" className="ghost fchip-clear" onClick={() => {
          pending.current = { key: null, index: 0 };
          onClearAll();
        }}>
          Clear all
        </button>
      )}
    </div>
  );
}

/** "+ Filter": opens a filters `details` and puts focus on its first control. The `toggle` event the browser
 *  fires keeps a controlled disclosure's state in step. */
export function revealFilters(details: HTMLDetailsElement | null) {
  if (!details) return;
  details.open = true;
  const first = details.querySelector<HTMLElement>(
    ":scope > :not(summary) :is(input, select, textarea, button):not(:disabled)",
  );
  first?.focus();
}
