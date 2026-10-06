import { useEffect, useId, useMemo, useRef, useState } from "react";

export interface FilterOption { value: string; label: string }

/** Up to this many options a native select is used; above it, a searchable list. */
export const SEARCHABLE_OVER = 15;

export const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

interface Props {
  label: string;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
  emptyLabel?: string;
  name?: string;
}

export default function FilterSelect(props: Props) {
  return props.options.length <= SEARCHABLE_OVER ? <NativeSelect {...props} /> : <Combo {...props} />;
}

function NativeSelect({ label, value, options, onChange, emptyLabel, name }: Props) {
  return (
    <label>
      {label}
      <select name={name} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{emptyLabel ?? "Any"}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

function Combo({ label, value, options, onChange, emptyLabel, name }: Props) {
  const uid = useId();
  const labelId = `${uid}-label`;
  const triggerId = `${uid}-trigger`;
  const listId = `${uid}-list`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const fieldRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const shown = useMemo(() => {
    const q = norm(query);
    return q ? options.filter((o) => norm(o.label).includes(q)) : options;
  }, [options, query]);
  const selected = options.find((o) => o.value === value);
  const activeId = active >= 0 && active < shown.length ? `${uid}-opt-${active}` : undefined;

  const reset = () => { setOpen(false); setQuery(""); setActive(-1); };

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (fieldRef.current && !fieldRef.current.contains(e.target as Node)) reset();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  useEffect(() => {
    if (activeId) document.getElementById(activeId)?.scrollIntoView?.({ block: "nearest" });
  }, [activeId]);

  const close = () => { reset(); triggerRef.current?.focus(); };
  const pick = (v: string) => { onChange(v); close(); };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const last = shown.length - 1;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => (last < 0 ? -1 : Math.min(a + 1, last))); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => (last < 0 ? -1 : Math.max(a - 1, 0))); }
    else if (e.key === "Home") { e.preventDefault(); setActive(last < 0 ? -1 : 0); }
    else if (e.key === "End") { e.preventDefault(); setActive(last); }
    else if (e.key === "Enter") { e.preventDefault(); if (activeId) pick(shown[active].value); }
    else if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "Tab") reset();
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
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-labelledby={`${labelId} ${triggerId}`}
          onClick={() => (open ? close() : setOpen(true))}
        >
          <span className="combo-value">{selected ? selected.label : (emptyLabel ?? "Any")}</span>
        </button>
        {value && (
          <button type="button" className="combo-clear" aria-label={`Clear ${label}`} onClick={() => { onChange(""); triggerRef.current?.focus(); }}>×</button>
        )}
      </div>
      {name && <input type="hidden" name={name} value={value} />}
      {open && (
        <div className="combo-popup">
          <input
            role="combobox"
            aria-label={`Search ${label}`}
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={activeId}
            aria-autocomplete="list"
            autoComplete="off"
            autoFocus
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActive(-1); }}
            onKeyDown={onKeyDown}
          />
          <div className="combo-count" aria-live="polite">{shown.length} of {options.length}</div>
          <ul role="listbox" id={listId} aria-label={label}>
            {shown.map((o, i) => (
              <li
                key={o.value}
                id={`${uid}-opt-${i}`}
                role="option"
                aria-selected={value === o.value}
                className={i === active ? "is-active" : undefined}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(o.value)}
              >
                {o.label}
              </li>
            ))}
          </ul>
          {shown.length === 0 && <div className="combo-empty">No matches</div>}
        </div>
      )}
    </div>
  );
}
