import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { api, errorMessage } from "../api/client";
import type { Facets, ProductPage } from "../api/types";
import { FilterSidebar } from "../components/FilterSidebar";
import { ProductCard, ProductCardSkeleton } from "../components/ProductCard";
import { EmptyState, ErrorState } from "../components/ui";
import { activeFilterCount, type Filters, PAGE_SIZE, parseFilters, SORTS, toApiQuery, toSearchParams } from "../lib/filters";

export function ProductsPage() {
  const [params, setParams] = useSearchParams();
  const filters = parseFilters(params);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const products = useQuery({
    queryKey: ["products", toApiQuery(filters)],
    queryFn: ({ signal }) => api<ProductPage>("/products", { query: toApiQuery(filters), signal }),
    placeholderData: keepPreviousData,
  });
  const facets = useQuery({ queryKey: ["facets"], queryFn: () => api<Facets>("/products/facets"), staleTime: 60_000 });

  function update(next: Partial<Filters>) {
    // Any filter change resets to page 1; page changes keep the other filters.
    const page = "page" in next ? next.page : 1;
    setParams(toSearchParams({ ...filters, ...next, page }));
    if ("page" in next) window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const data = products.data;
  const heading = filters.q ? `Results for “${filters.q}”` : filters.category.length === 1 ? filters.category[0] : "Products";
  const sidebar = <FilterSidebar filters={filters} facets={facets.data} onChange={update} />;

  return (
    <div className="flex gap-6">
      <div className="hidden w-72 shrink-0 lg:block">{sidebar}</div>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Filters">
          <button type="button" className="absolute inset-0 bg-black/30" aria-label="Close filters" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[85%] max-w-sm overflow-y-auto bg-canvas p-3">
            <button type="button" className="btn-ghost mb-2" onClick={() => setDrawerOpen(false)}>
              <X className="h-4 w-4" aria-hidden="true" /> Close
            </button>
            {sidebar}
          </div>
        </div>
      )}

      <section className="min-w-0 flex-1" aria-labelledby="products-heading">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 id="products-heading" className="text-2xl font-semibold">{heading}</h1>
            <p className="text-sm text-muted" aria-live="polite">
              {data ? <>Showing {data.total.toLocaleString("en-IN")} products{filters.category.length > 0 && (
                <> in <span className="font-medium text-brand-700">{filters.category.join(", ")}</span></>)}</> : "Loading products…"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" className="btn-outline lg:hidden" onClick={() => setDrawerOpen(true)}>
              <SlidersHorizontal className="h-4 w-4" aria-hidden="true" /> Filters
              {activeFilterCount(filters) > 0 && <span className="rounded-full bg-brand-600 px-1.5 text-xs text-white">{activeFilterCount(filters)}</span>}
            </button>
            <label className="flex items-center gap-2 text-sm text-muted">
              Sort by
              <select className="input w-auto py-1.5" value={filters.sort}
                onChange={(e) => update({ sort: e.target.value as Filters["sort"] })}>
                {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </label>
          </div>
        </div>

        {products.isError ? (
          <ErrorState message={errorMessage(products.error)} onRetry={() => products.refetch()} />
        ) : !data ? (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {Array.from({ length: PAGE_SIZE }, (_, i) => <ProductCardSkeleton key={i} />)}
          </div>
        ) : data.items.length === 0 ? (
          <EmptyState title="No products match your filters"
            action={<button type="button" className="btn-primary" onClick={() => setParams(new URLSearchParams())}>Clear search & filters</button>}>
            Try removing a filter or searching for something else.
          </EmptyState>
        ) : (
          <>
            <ul className={`grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 ${products.isFetching ? "opacity-70" : ""}`}
              aria-busy={products.isFetching}>
              {data.items.map((p) => <li key={p.id} className="flex"><ProductCard product={p} /></li>)}
            </ul>
            {data.total_pages > 1 && (
              <nav aria-label="Pagination" className="mt-8 flex items-center justify-center gap-2">
                <button type="button" className="btn-outline" disabled={data.page <= 1} onClick={() => update({ page: data.page - 1 })}>
                  <ChevronLeft className="h-4 w-4" aria-hidden="true" /> Previous
                </button>
                <span className="px-3 text-sm text-muted">Page {data.page} of {data.total_pages}</span>
                <button type="button" className="btn-outline" disabled={data.page >= data.total_pages} onClick={() => update({ page: data.page + 1 })}>
                  Next <ChevronRight className="h-4 w-4" aria-hidden="true" />
                </button>
              </nav>
            )}
          </>
        )}
      </section>
    </div>
  );
}
