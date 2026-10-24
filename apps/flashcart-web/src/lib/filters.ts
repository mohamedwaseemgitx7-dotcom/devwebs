/** Product filters are stored in the URL (shareable, back-button friendly) and validated on the way in. */
import type { Category, Color, Shipping, SortKey } from "../api/types";

export const CATEGORIES: Category[] = ["Electronics", "Fashion", "Foods", "Furniture", "Tools"];
export const COLORS: Color[] = ["red", "blue", "orange", "black", "white", "green", "grey"];
export const SHIPPING: Shipping[] = ["regular", "economic", "next_day", "instant"];
export const SORTS: { value: SortKey; label: string }[] = [
  { value: "rating", label: "Ratings" },
  { value: "popular", label: "Most popular" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "newest", label: "Newest" },
];
export const PRICE_PRESETS: { label: string; min?: number; max?: number }[] = [
  { label: "Under ₹500", max: 500 },
  { label: "₹500 – ₹2,000", min: 500, max: 2000 },
  { label: "₹2,000 – ₹5,000", min: 2000, max: 5000 },
  { label: "Over ₹5,000", min: 5000 },
];
export const RATINGS = [4.5, 4, 3.5, 3];
export const PAGE_SIZE = 12;

export interface Filters {
  q: string;
  category: Category[];
  color: Color[];
  shipping: Shipping[];
  minPrice?: number; // rupees
  maxPrice?: number; // rupees
  minRating?: number;
  inStock: boolean;
  sort: SortKey;
  page: number;
}

function num(value: string | null, min: number, max: number): number | undefined {
  if (value === null || value.trim() === "") return undefined;
  const n = Number(value);
  return Number.isFinite(n) && n >= min && n <= max ? n : undefined;
}

export function parseFilters(params: URLSearchParams): Filters {
  const sort = params.get("sort") as SortKey | null;
  return {
    q: (params.get("q") ?? "").slice(0, 100),
    category: params.getAll("category").filter((c): c is Category => CATEGORIES.includes(c as Category)),
    color: params.getAll("color").filter((c): c is Color => COLORS.includes(c as Color)),
    shipping: params.getAll("shipping").filter((s): s is Shipping => SHIPPING.includes(s as Shipping)),
    minPrice: num(params.get("min_price"), 0, 1_000_000),
    maxPrice: num(params.get("max_price"), 0, 1_000_000),
    minRating: num(params.get("min_rating"), 0, 5),
    inStock: params.get("in_stock") === "1",
    sort: sort && SORTS.some((s) => s.value === sort) ? sort : "rating",
    page: Math.min(200, Math.max(1, Math.floor(num(params.get("page"), 1, 200) ?? 1))),
  };
}

export function toSearchParams(f: Partial<Filters>): URLSearchParams {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  f.category?.forEach((c) => p.append("category", c));
  f.color?.forEach((c) => p.append("color", c));
  f.shipping?.forEach((s) => p.append("shipping", s));
  if (f.minPrice !== undefined) p.set("min_price", String(f.minPrice));
  if (f.maxPrice !== undefined) p.set("max_price", String(f.maxPrice));
  if (f.minRating !== undefined) p.set("min_rating", String(f.minRating));
  if (f.inStock) p.set("in_stock", "1");
  if (f.sort && f.sort !== "rating") p.set("sort", f.sort);
  if (f.page && f.page > 1) p.set("page", String(f.page));
  return p;
}

/** Query for GET /api/v1/products (prices converted to paise). */
export function toApiQuery(f: Filters) {
  return {
    q: f.q || undefined,
    category: f.category,
    color: f.color,
    shipping: f.shipping,
    min_price: f.minPrice !== undefined ? Math.round(f.minPrice * 100) : undefined,
    max_price: f.maxPrice !== undefined ? Math.round(f.maxPrice * 100) : undefined,
    min_rating: f.minRating,
    in_stock: f.inStock || undefined,
    sort: f.sort,
    page: f.page,
    page_size: PAGE_SIZE,
  };
}

export function activeFilterCount(f: Filters): number {
  return f.category.length + f.color.length + f.shipping.length + (f.minPrice !== undefined || f.maxPrice !== undefined ? 1 : 0)
    + (f.minRating !== undefined ? 1 : 0) + (f.inStock ? 1 : 0);
}
