import { useQuery } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router";
import { ApiError, api, errorMessage } from "../api/client";
import type { Order, OrderPage } from "../api/types";
import { EmptyState, ErrorState, Spinner } from "../components/ui";
import { formatDate, formatPrice, SHIPPING_LABELS, STATUS_LABELS } from "../lib/format";

export function StatusBadge({ status }: { status: string }) {
  const style: Record<string, string> = {
    confirmed: "bg-blue-50 text-blue-700", paid: "bg-brand-50 text-brand-700", shipped: "bg-amber-50 text-amber-700",
    delivered: "bg-green-50 text-green-700", cancelled: "bg-red-50 text-red-700",
  };
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${style[status] ?? ""}`}>{STATUS_LABELS[status] ?? status}</span>;
}

export function OrdersPage() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const orders = useQuery({ queryKey: ["orders", page], queryFn: () => api<OrderPage>("/orders", { query: { page } }) });

  if (orders.isLoading) return <Spinner label="Loading your orders" />;
  if (orders.isError) return <ErrorState message={errorMessage(orders.error)} onRetry={() => orders.refetch()} />;
  const data = orders.data!;
  if (data.total === 0) {
    return <EmptyState title="No orders yet" action={<Link to="/products" className="btn-primary">Start shopping</Link>} />;
  }
  const pages = Math.ceil(data.total / data.page_size);
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-4 text-2xl font-semibold">My orders</h1>
      <ul className="space-y-3">
        {data.items.map((o) => (
          <li key={o.id}>
            <Link to={`/orders/${o.id}`} className="card flex flex-wrap items-center justify-between gap-3 p-4 hover:border-brand-500">
              <div>
                <p className="font-semibold">{o.order_number}</p>
                <p className="text-sm text-muted">{formatDate(o.created_at)} · {o.items.reduce((s, i) => s + i.quantity, 0)} items</p>
              </div>
              <div className="flex items-center gap-4">
                <StatusBadge status={o.status} />
                <span className="font-semibold">{formatPrice(o.total_paise)}</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
      {pages > 1 && (
        <nav aria-label="Pagination" className="mt-6 flex justify-center gap-2">
          <button type="button" className="btn-outline" disabled={page <= 1} onClick={() => setParams({ page: String(page - 1) })}>Previous</button>
          <span className="px-3 py-2 text-sm text-muted">Page {page} of {pages}</span>
          <button type="button" className="btn-outline" disabled={page >= pages} onClick={() => setParams({ page: String(page + 1) })}>Next</button>
        </nav>
      )}
    </div>
  );
}

export function OrderDetailPage() {
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const order = useQuery({
    queryKey: ["order", id],
    queryFn: () => api<Order>(`/orders/${encodeURIComponent(id)}`),
    retry: (n, err) => !(err instanceof ApiError && err.status === 404) && n < 2,
  });
  if (order.isLoading) return <Spinner label="Loading order" />;
  if (order.isError) {
    return order.error instanceof ApiError && order.error.status === 404
      ? <EmptyState title="Order not found" action={<Link to="/orders" className="btn-primary">My orders</Link>} />
      : <ErrorState message={errorMessage(order.error)} onRetry={() => order.refetch()} />;
  }
  const o = order.data!;
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      {params.get("placed") === "1" && (
        <div role="status" className="card flex items-center gap-4 border-brand-200 bg-brand-50 p-5">
          <CheckCircle2 className="h-10 w-10 shrink-0 text-brand-600" aria-hidden="true" />
          <div>
            <h1 className="text-xl font-semibold">Thank you! Your order is confirmed.</h1>
            <p className="text-sm text-muted">Order {o.order_number} · a confirmation would be emailed in a real store.</p>
          </div>
        </div>
      )}
      <section className="card p-5" aria-labelledby="order-heading">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="order-heading" className="text-lg font-semibold">Order {o.order_number}</h2>
          <StatusBadge status={o.status} />
        </div>
        <p className="text-sm text-muted">Placed {formatDate(o.created_at)} · {SHIPPING_LABELS[o.shipping_method]} delivery</p>
        <table className="mt-4 w-full text-sm">
          <caption className="sr-only">Items in this order</caption>
          <thead><tr className="text-left text-muted"><th className="py-2 font-medium">Item</th><th className="font-medium">Qty</th><th className="text-right font-medium">Total</th></tr></thead>
          <tbody className="divide-y divide-line">
            {o.items.map((i) => (
              <tr key={i.product_id}>
                <td className="py-2">{i.name}<br /><span className="text-xs text-muted">{formatPrice(i.unit_price_paise)} each</span></td>
                <td>{i.quantity}</td>
                <td className="text-right">{formatPrice(i.line_total_paise)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="border-t border-line">
            <tr><td colSpan={2} className="pt-2 text-muted">Subtotal</td><td className="pt-2 text-right">{formatPrice(o.subtotal_paise)}</td></tr>
            <tr><td colSpan={2} className="text-muted">Shipping</td><td className="text-right">{o.shipping_paise ? formatPrice(o.shipping_paise) : "Free"}</td></tr>
            <tr className="font-semibold"><td colSpan={2}>Total</td><td className="text-right">{formatPrice(o.total_paise)}</td></tr>
          </tfoot>
        </table>
      </section>
      <section className="card p-5 text-sm" aria-label="Shipping address">
        <h2 className="mb-1 font-semibold">Ship to</h2>
        <p>{o.shipping_address.full_name}<br />{o.shipping_address.line1}<br />{o.shipping_address.city} {o.shipping_address.postal_code}<br />{o.shipping_address.phone}</p>
      </section>
      <div className="flex gap-3">
        <Link to="/orders" className="btn-outline">All orders</Link>
        <Link to="/products" className="btn-primary">Continue shopping</Link>
      </div>
    </div>
  );
}
