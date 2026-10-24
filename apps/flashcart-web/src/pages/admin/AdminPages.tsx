import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, IndianRupee, Package, ShoppingCart, Users } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link, NavLink, useSearchParams } from "react-router";
import { ApiError, api, errorMessage } from "../../api/client";
import type { AdminStats, Category, OrderPage, OrderStatus, Product } from "../../api/types";
import { Alert, ErrorState, Spinner } from "../../components/ui";
import { CATEGORIES } from "../../lib/filters";
import { formatDate, formatPrice, STATUS_LABELS } from "../../lib/format";
import { StatusBadge } from "../OrdersPage";

function AdminNav() {
  const cls = ({ isActive }: { isActive: boolean }) => `rounded-lg px-3 py-1.5 text-sm ${isActive ? "bg-brand-600 text-white" : "hover:bg-brand-50"}`;
  return (
    <nav aria-label="Admin" className="mb-6 flex flex-wrap gap-2">
      <NavLink end to="/admin" className={cls}>Dashboard</NavLink>
      <NavLink to="/admin/products" className={cls}>Products & inventory</NavLink>
      <NavLink to="/admin/orders" className={cls}>Orders</NavLink>
    </nav>
  );
}

function Stat({ icon, label, value, tone = "" }: { icon: ReactNode; label: string; value: ReactNode; tone?: string }) {
  return (
    <div className="card flex items-center gap-4 p-5">
      <span className={`flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-700 ${tone}`}>{icon}</span>
      <div><p className="text-sm text-muted">{label}</p><p className="text-2xl font-semibold">{value}</p></div>
    </div>
  );
}

export function AdminDashboard() {
  const stats = useQuery({ queryKey: ["admin", "stats"], queryFn: () => api<AdminStats>("/admin/stats") });
  const lowStock = useQuery({ queryKey: ["admin", "low-stock"], queryFn: () => api<Product[]>("/admin/products", { query: { low_stock_below: 5, include_inactive: false } }) });
  const recent = useQuery({ queryKey: ["admin", "orders", "recent"], queryFn: () => api<OrderPage>("/admin/orders", { query: { page_size: 5 } }) });

  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold">Admin dashboard</h1>
      <AdminNav />
      {stats.isError ? <ErrorState message={errorMessage(stats.error)} onRetry={() => stats.refetch()} /> : !stats.data ? <Spinner /> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat icon={<IndianRupee className="h-5 w-5" />} label="Revenue (30 days)" value={formatPrice(stats.data.last_30_days.revenue_paise)} />
          <Stat icon={<ShoppingCart className="h-5 w-5" />} label="Orders (30 days)" value={stats.data.last_30_days.orders} />
          <Stat icon={<Users className="h-5 w-5" />} label="Customers" value={stats.data.customers} />
          <Stat icon={<AlertTriangle className="h-5 w-5" />} label="Low-stock products" value={stats.data.low_stock}
            tone={stats.data.low_stock ? "bg-orange-50 text-orange-600" : ""} />
        </div>
      )}
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <section className="card p-5" aria-labelledby="recent-heading">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="recent-heading" className="font-semibold">Recent orders</h2>
            <Link to="/admin/orders" className="text-sm text-brand-700 underline">All orders</Link>
          </div>
          {recent.data?.items.length === 0 && <p className="text-sm text-muted">No orders yet.</p>}
          <ul className="divide-y divide-line text-sm">
            {recent.data?.items.map((o) => (
              <li key={o.id} className="flex items-center justify-between gap-3 py-2">
                <span><span className="font-medium">{o.order_number}</span><br /><span className="text-xs text-muted">{o.user_email}</span></span>
                <StatusBadge status={o.status} />
                <span className="font-medium">{formatPrice(o.total_paise)}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="card p-5" aria-labelledby="low-heading">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="low-heading" className="font-semibold">Low stock (under 5)</h2>
            <Link to="/admin/products" className="text-sm text-brand-700 underline">Manage inventory</Link>
          </div>
          {lowStock.data?.length === 0 && <p className="text-sm text-muted">All products are well stocked.</p>}
          <ul className="divide-y divide-line text-sm">
            {lowStock.data?.map((p) => (
              <li key={p.id} className="flex justify-between py-2"><span>{p.name}</span>
                <span className={p.stock === 0 ? "font-semibold text-danger" : "text-orange-600"}>{p.stock} left</span></li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

function ProductRow({ product }: { product: Product }) {
  const queryClient = useQueryClient();
  const [price, setPrice] = useState(String(product.price_paise / 100));
  const [syncedVersion, setSyncedVersion] = useState(product.version);
  // Rows are keyed by id (not id+version) so a refresh after saving does not remount the row and wipe the
  // confirmation message (TROUBLESHOOTING TS-010). Re-sync the editable price when the server version changes.
  if (product.version !== syncedVersion) {
    setSyncedVersion(product.version);
    setPrice(String(product.price_paise / 100));
  }
  const [delta, setDelta] = useState("");
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["admin"] });
    queryClient.invalidateQueries({ queryKey: ["products"] });
  };
  const handle = (err: unknown) => setMessage({
    kind: "error",
    text: err instanceof ApiError && err.status === 409 ? `${errorMessage(err)} (list refreshed)` : errorMessage(err),
  });

  const savePrice = useMutation({
    mutationFn: () => api<Product>(`/admin/products/${product.id}`, {
      method: "PATCH", body: { version: product.version, price_paise: Math.round(Number(price) * 100) },
    }),
    onSuccess: () => { setMessage({ kind: "success", text: "Price saved" }); refresh(); },
    onError: (err) => { handle(err); refresh(); },
  });
  const adjust = useMutation({
    mutationFn: () => api<Product>(`/admin/products/${product.id}/stock`, {
      method: "POST", body: { delta: Number(delta), reason: "Manual adjustment from admin dashboard" },
    }),
    onSuccess: (p) => { setDelta(""); setMessage({ kind: "success", text: `Stock is now ${p.stock}` }); refresh(); },
    onError: handle,
  });
  const toggleActive = useMutation({
    mutationFn: () => api<Product>(`/admin/products/${product.id}`, {
      method: "PATCH", body: { version: product.version, active: !product.active },
    }),
    onSuccess: refresh,
    onError: handle,
  });

  return (
    <tr className="align-top">
      <td className="py-3 pr-3">
        <p className="font-medium">{product.name}{!product.active && <span className="ml-2 rounded bg-line px-1.5 text-xs text-muted">Hidden</span>}</p>
        <p className="text-xs text-muted">{product.sku} · {product.category} · v{product.version}</p>
        {message && <p role={message.kind === "error" ? "alert" : "status"} className={`mt-1 text-xs ${message.kind === "error" ? "text-danger" : "text-brand-700"}`}>{message.text}</p>}
      </td>
      <td className="py-3 pr-3">
        <form className="flex gap-1" onSubmit={(e) => { e.preventDefault(); savePrice.mutate(); }}>
          <label className="sr-only" htmlFor={`price-${product.id}`}>Price in rupees for {product.name}</label>
          <input id={`price-${product.id}`} className="input w-24 py-1" inputMode="decimal" value={price}
            onChange={(e) => setPrice(e.target.value.replace(/[^0-9.]/g, ""))} />
          <button type="submit" className="btn-outline px-2 py-1" disabled={savePrice.isPending || Number(price) * 100 === product.price_paise}>Save</button>
        </form>
      </td>
      <td className="py-3 pr-3">
        <span className={`font-semibold ${product.stock === 0 ? "text-danger" : product.stock < 5 ? "text-orange-600" : ""}`}>{product.stock}</span>
        <form className="mt-1 flex gap-1" onSubmit={(e) => { e.preventDefault(); adjust.mutate(); }}>
          <label className="sr-only" htmlFor={`delta-${product.id}`}>Stock change for {product.name}</label>
          <input id={`delta-${product.id}`} className="input w-20 py-1" placeholder="+/-" value={delta}
            onChange={(e) => setDelta(e.target.value.replace(/[^0-9-]/g, ""))} />
          <button type="submit" className="btn-outline px-2 py-1" disabled={!delta || delta === "-" || adjust.isPending}>Apply</button>
        </form>
      </td>
      <td className="py-3">
        <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => toggleActive.mutate()}>
          {product.active ? "Hide" : "Show"}
        </button>
      </td>
    </tr>
  );
}

function NewProductForm() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ sku: "", name: "", brand: "", category: "Electronics" as Category, price: "", stock: "" });
  const [error, setError] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => api<Product>("/admin/products", {
      method: "POST",
      body: { sku: form.sku.toUpperCase(), name: form.name, brand: form.brand, category: form.category,
        price_paise: Math.round(Number(form.price) * 100), stock: Number(form.stock), shipping: ["regular"] },
    }),
    onSuccess: () => {
      setForm({ sku: "", name: "", brand: "", category: "Electronics", price: "", stock: "" });
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["admin"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (err) => setError(errorMessage(err)),
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }
  return (
    <form onSubmit={submit} className="card mb-6 grid gap-3 p-5 sm:grid-cols-3 lg:grid-cols-7" aria-label="Add product">
      <h2 className="font-semibold sm:col-span-3 lg:col-span-7">Add a product</h2>
      {error && <div className="sm:col-span-3 lg:col-span-7"><Alert>{error}</Alert></div>}
      {(["sku", "name", "brand"] as const).map((k) => (
        <label key={k} className="text-xs text-muted">{k.toUpperCase()}
          <input className="input mt-1" required value={form[k]} maxLength={k === "sku" ? 40 : 120}
            onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
        </label>
      ))}
      <label className="text-xs text-muted">CATEGORY
        <select className="input mt-1" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as Category })}>
          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <label className="text-xs text-muted">PRICE ₹
        <input className="input mt-1" required inputMode="decimal" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value.replace(/[^0-9.]/g, "") })} />
      </label>
      <label className="text-xs text-muted">STOCK
        <input className="input mt-1" required inputMode="numeric" value={form.stock} onChange={(e) => setForm({ ...form, stock: e.target.value.replace(/\D/g, "") })} />
      </label>
      <button type="submit" className="btn-primary self-end" disabled={create.isPending}>{create.isPending ? "Adding…" : "Add"}</button>
    </form>
  );
}

export function AdminProducts() {
  const [lowOnly, setLowOnly] = useState(false);
  const products = useQuery({
    queryKey: ["admin", "products", lowOnly],
    queryFn: () => api<Product[]>("/admin/products", { query: { low_stock_below: lowOnly ? 5 : undefined } }),
  });
  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold">Products & inventory</h1>
      <AdminNav />
      <NewProductForm />
      <label className="mb-3 flex items-center gap-2 text-sm">
        <input type="checkbox" className="accent-brand-600" checked={lowOnly} onChange={() => setLowOnly(!lowOnly)} /> Show low stock only
      </label>
      {products.isError ? <ErrorState message={errorMessage(products.error)} onRetry={() => products.refetch()} /> : !products.data ? <Spinner /> : (
        <div className="card overflow-x-auto p-4">
          <table className="w-full min-w-[640px] text-sm">
            <caption className="sr-only">Products</caption>
            <thead><tr className="text-left text-muted"><th className="pb-2 font-medium">Product</th><th className="pb-2 font-medium">Price (₹)</th>
              <th className="pb-2 font-medium">Stock</th><th className="pb-2 font-medium">Visibility</th></tr></thead>
            <tbody className="divide-y divide-line">
              {products.data.map((p) => <ProductRow key={p.id} product={p} />)}
            </tbody>
          </table>
          <p className="mt-3 flex items-center gap-1 text-xs text-muted"><Package className="h-3 w-3" aria-hidden="true" />
            Edits use optimistic locking: if someone else changed a product first, you’ll be asked to reload.</p>
        </div>
      )}
    </div>
  );
}

const NEXT_STATUS: Record<OrderStatus, OrderStatus[]> = {
  confirmed: ["paid", "shipped", "cancelled"], paid: ["shipped", "cancelled"], shipped: ["delivered"], delivered: [], cancelled: [],
};

export function AdminOrders() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const orders = useQuery({
    queryKey: ["admin", "orders", status, page],
    queryFn: () => api<OrderPage>("/admin/orders", { query: { status: status || undefined, page } }),
  });
  const update = useMutation({
    mutationFn: ({ id, next }: { id: string; next: OrderStatus }) => api(`/admin/orders/${id}`, { method: "PATCH", body: { status: next } }),
    onSuccess: () => { setError(null); queryClient.invalidateQueries({ queryKey: ["admin"] }); },
    onError: (err) => setError(errorMessage(err)),
  });
  const pages = orders.data ? Math.max(1, Math.ceil(orders.data.total / orders.data.page_size)) : 1;

  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold">Orders</h1>
      <AdminNav />
      <label className="mb-4 flex items-center gap-2 text-sm">Status
        <select className="input w-auto py-1.5" value={status} onChange={(e) => setParams(e.target.value ? { status: e.target.value } : {})}>
          <option value="">All</option>
          {Object.entries(STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>
      {error && <div className="mb-3"><Alert>{error}</Alert></div>}
      {orders.isError ? <ErrorState message={errorMessage(orders.error)} onRetry={() => orders.refetch()} /> : !orders.data ? <Spinner /> : (
        <div className="card overflow-x-auto p-4">
          <table className="w-full min-w-[720px] text-sm">
            <caption className="sr-only">Orders</caption>
            <thead><tr className="text-left text-muted"><th className="pb-2 font-medium">Order</th><th className="pb-2 font-medium">Customer</th>
              <th className="pb-2 font-medium">Total</th><th className="pb-2 font-medium">Status</th><th className="pb-2 font-medium">Change status</th></tr></thead>
            <tbody className="divide-y divide-line">
              {orders.data.items.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-muted">No orders.</td></tr>}
              {orders.data.items.map((o) => (
                <tr key={o.id}>
                  <td className="py-2"><span className="font-medium">{o.order_number}</span><br /><span className="text-xs text-muted">{formatDate(o.created_at)}</span></td>
                  <td>{o.user_email}</td>
                  <td>{formatPrice(o.total_paise)}</td>
                  <td><StatusBadge status={o.status} /></td>
                  <td className="space-x-1">
                    {NEXT_STATUS[o.status].length === 0 && <span className="text-xs text-muted">Final</span>}
                    {NEXT_STATUS[o.status].map((n) => (
                      <button key={n} type="button" className={`btn-outline px-2 py-1 text-xs ${n === "cancelled" ? "text-danger" : ""}`}
                        disabled={update.isPending}
                        onClick={() => (n !== "cancelled" || window.confirm(`Cancel ${o.order_number}? Stock will be returned.`)) && update.mutate({ id: o.id, next: n })}>
                        {STATUS_LABELS[n]}
                      </button>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {pages > 1 && (
            <nav aria-label="Pagination" className="mt-4 flex justify-center gap-2">
              <button type="button" className="btn-outline" disabled={page <= 1} onClick={() => setParams({ ...(status && { status }), page: String(page - 1) })}>Previous</button>
              <span className="px-3 py-2 text-sm text-muted">Page {page} of {pages}</span>
              <button type="button" className="btn-outline" disabled={page >= pages} onClick={() => setParams({ ...(status && { status }), page: String(page + 1) })}>Next</button>
            </nav>
          )}
        </div>
      )}
    </div>
  );
}
