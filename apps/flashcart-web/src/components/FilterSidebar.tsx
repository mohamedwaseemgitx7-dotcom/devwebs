import { ChevronDown, SlidersHorizontal, Star, X } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import type { Facets } from "../api/types";
import { SHIPPING_LABELS } from "../lib/format";
import { CATEGORIES, COLORS, type Filters, PRICE_PRESETS, RATINGS, SHIPPING } from "../lib/filters";

const SWATCH: Record<string, string> = {
  red: "#d64545", blue: "#2f9fdb", orange: "#e8833a", black: "#1f2328", white: "#ffffff", green: "#2e9e6b",
  grey: "#8a94a3",
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(true);
  const id = `filter-${title.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <section className="border-t border-line py-4 first:border-t-0">
      <h3>
        <button type="button" className="flex w-full items-center justify-between font-semibold" aria-expanded={open}
          aria-controls={id} onClick={() => setOpen(!open)}>
          {title}
          <ChevronDown className={`h-4 w-4 text-muted transition-transform ${open ? "" : "-rotate-90"}`} aria-hidden="true" />
        </button>
      </h3>
      <div id={id} hidden={!open} className="mt-3">{children}</div>
    </section>
  );
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export function FilterSidebar({ filters, facets, onChange }: {
  filters: Filters;
  facets?: Facets;
  onChange: (next: Partial<Filters>) => void;
}) {
  const urlMin = filters.minPrice?.toString() ?? "";
  const urlMax = filters.maxPrice?.toString() ?? "";
  const [minDraft, setMinDraft] = useState(urlMin);
  const [maxDraft, setMaxDraft] = useState(urlMax);
  const [synced, setSynced] = useState(`${urlMin}|${urlMax}`);
  // Re-sync the price inputs when the URL changes (back button, chip removal) WITHOUT remounting the sidebar —
  // remounting would drop keyboard focus after every filter click.
  if (`${urlMin}|${urlMax}` !== synced) {
    setSynced(`${urlMin}|${urlMax}`);
    setMinDraft(urlMin);
    setMaxDraft(urlMax);
  }
  const counts = new Map(facets?.categories.map((c) => [c.value, c.count]));

  const chips: { label: string; clear: Partial<Filters> }[] = [
    ...filters.category.map((c) => ({ label: `Category: ${c}`, clear: { category: filters.category.filter((x) => x !== c) } })),
    ...filters.color.map((c) => ({ label: `Color: ${c}`, clear: { color: filters.color.filter((x) => x !== c) } })),
    ...filters.shipping.map((s) => ({ label: `Shipping: ${SHIPPING_LABELS[s]}`, clear: { shipping: filters.shipping.filter((x) => x !== s) } })),
    ...(filters.minPrice !== undefined || filters.maxPrice !== undefined
      ? [{ label: `Price: ₹${filters.minPrice ?? 0} – ${filters.maxPrice !== undefined ? `₹${filters.maxPrice}` : "any"}`,
          clear: { minPrice: undefined, maxPrice: undefined } }]
      : []),
    ...(filters.minRating !== undefined ? [{ label: `Rating ≥ ${filters.minRating}`, clear: { minRating: undefined } }] : []),
    ...(filters.inStock ? [{ label: "In stock", clear: { inStock: false } }] : []),
  ];

  function applyPrice(e: FormEvent) {
    e.preventDefault();
    const min = minDraft === "" ? undefined : Math.max(0, Number(minDraft));
    const max = maxDraft === "" ? undefined : Math.max(0, Number(maxDraft));
    if ((min !== undefined && Number.isNaN(min)) || (max !== undefined && Number.isNaN(max))) return;
    onChange(min !== undefined && max !== undefined && min > max ? { minPrice: max, maxPrice: min } : { minPrice: min, maxPrice: max });
  }

  return (
    <aside aria-label="Product filters" className="card p-5">
      <div className="flex items-center justify-between pb-3">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <SlidersHorizontal className="h-4 w-4" aria-hidden="true" /> Filters
        </h2>
        {chips.length > 0 && (
          <button type="button" className="text-sm font-medium text-brand-700 underline underline-offset-2"
            onClick={() => {
              setMinDraft("");
              setMaxDraft("");
              onChange({ category: [], color: [], shipping: [], minPrice: undefined, maxPrice: undefined, minRating: undefined, inStock: false });
            }}>
            Clear All
          </button>
        )}
      </div>
      {chips.length > 0 && (
        <ul className="flex flex-wrap gap-2 pb-3" aria-label="Active filters">
          {chips.map((chip) => (
            <li key={chip.label}>
              <button type="button" className="chip bg-canvas hover:border-brand-500" onClick={() => onChange(chip.clear)}
                aria-label={`Remove filter ${chip.label}`}>
                {chip.label} <X className="h-3 w-3 text-brand-700" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <Section title="Category">
        <fieldset className="space-y-2">
          <legend className="sr-only">Category</legend>
          {CATEGORIES.map((c) => (
            <label key={c} className="flex cursor-pointer items-center gap-3 text-sm">
              <input type="checkbox" className="h-4 w-4 accent-brand-600" checked={filters.category.includes(c)}
                onChange={() => onChange({ category: toggle(filters.category, c) })} />
              <span className="flex-1">{c}</span>
              {counts.has(c) && <span className="text-xs text-muted">{counts.get(c)}</span>}
            </label>
          ))}
        </fieldset>
      </Section>

      <Section title="Price">
        <div className="space-y-2">
          {PRICE_PRESETS.map((p) => {
            const active = filters.minPrice === p.min && filters.maxPrice === p.max;
            return (
              <label key={p.label} className="flex cursor-pointer items-center gap-3 text-sm">
                <input type="radio" name="price-preset" className="h-4 w-4 accent-brand-600" checked={active}
                  onChange={() => {
                    setMinDraft(p.min?.toString() ?? "");
                    setMaxDraft(p.max?.toString() ?? "");
                    onChange({ minPrice: p.min, maxPrice: p.max });
                  }} />
                {p.label}
              </label>
            );
          })}
        </div>
        <form className="mt-3 flex items-end gap-2" onSubmit={applyPrice}>
          <label className="flex-1 text-xs text-muted">
            Min ₹
            <input className="input mt-1" inputMode="numeric" value={minDraft} onChange={(e) => setMinDraft(e.target.value.replace(/\D/g, ""))} />
          </label>
          <span className="pb-2 text-muted">–</span>
          <label className="flex-1 text-xs text-muted">
            Max ₹
            <input className="input mt-1" inputMode="numeric" value={maxDraft} onChange={(e) => setMaxDraft(e.target.value.replace(/\D/g, ""))} />
          </label>
          <button type="submit" className="btn-outline px-3">Go</button>
        </form>
      </Section>

      <Section title="Color">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Color">
          {COLORS.map((c) => {
            const on = filters.color.includes(c);
            return (
              <button key={c} type="button" aria-pressed={on} onClick={() => onChange({ color: toggle(filters.color, c) })}
                className={`chip capitalize ${on ? "border-brand-600 bg-brand-600 text-white" : "hover:border-brand-500"}`}>
                <span className="h-3 w-3 rounded-full border border-black/10" style={{ background: SWATCH[c] }} aria-hidden="true" />
                {c}
              </button>
            );
          })}
        </div>
      </Section>

      <Section title="Rating">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Minimum rating">
          {RATINGS.map((r) => {
            const on = filters.minRating === r;
            return (
              <button key={r} type="button" aria-pressed={on} onClick={() => onChange({ minRating: on ? undefined : r })}
                className={`chip ${on ? "border-brand-600 bg-brand-600 text-white" : "hover:border-brand-500"}`}>
                {r}+ <Star className={`h-3 w-3 ${on ? "fill-white" : "fill-star text-star"}`} aria-hidden="true" />
                <span className="sr-only">stars</span>
              </button>
            );
          })}
        </div>
      </Section>

      <Section title="Shipping Options">
        <fieldset className="space-y-2">
          <legend className="sr-only">Shipping options</legend>
          {SHIPPING.map((s) => (
            <label key={s} className="flex cursor-pointer items-center gap-3 text-sm">
              <input type="checkbox" className="h-4 w-4 accent-brand-600" checked={filters.shipping.includes(s)}
                onChange={() => onChange({ shipping: toggle(filters.shipping, s) })} />
              {SHIPPING_LABELS[s]}
            </label>
          ))}
        </fieldset>
      </Section>

      <Section title="Availability">
        <label className="flex cursor-pointer items-center gap-3 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-brand-600" checked={filters.inStock}
            onChange={() => onChange({ inStock: !filters.inStock })} />
          In stock only
        </label>
      </Section>
    </aside>
  );
}
