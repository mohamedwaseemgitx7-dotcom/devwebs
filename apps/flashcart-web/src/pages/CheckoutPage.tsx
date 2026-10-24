import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";
import { ApiError, api, errorMessage } from "../api/client";
import type { Address, Cart, Order, Shipping, ShortageDetail } from "../api/types";
import { Alert, EmptyState, ErrorState, Spinner } from "../components/ui";
import { formatPrice, SHIPPING_LABELS } from "../lib/format";

const METHODS: { value: Shipping; eta: string }[] = [
  { value: "economic", eta: "5–7 days" },
  { value: "regular", eta: "3–5 days" },
  { value: "next_day", eta: "Next day" },
  { value: "instant", eta: "Within 4 hours (select cities)" },
];

const EMPTY: Address = { full_name: "", line1: "", city: "", postal_code: "", phone: "" };

function newKey(): string {
  return crypto.randomUUID().replace(/-/g, "");
}

function validate(a: Address): Partial<Record<keyof Address, string>> {
  const errors: Partial<Record<keyof Address, string>> = {};
  if (!a.full_name.trim()) errors.full_name = "Enter the recipient's name";
  if (!a.line1.trim()) errors.line1 = "Enter the street address";
  if (!a.city.trim()) errors.city = "Enter the city";
  if (!/^[0-9]{6}$/.test(a.postal_code)) errors.postal_code = "PIN code must be 6 digits";
  if (!/^[6-9][0-9]{9}$/.test(a.phone)) errors.phone = "Enter a 10-digit Indian mobile number";
  return errors;
}

export function CheckoutPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [method, setMethod] = useState<Shipping>("regular");
  const [address, setAddress] = useState<Address>(EMPTY);
  const [touched, setTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ShortageDetail | string | null>(null);
  // One idempotency key per checkout attempt: retries after a network error reuse it, so the server returns the
  // same order instead of creating a duplicate. A new key is generated only after the cart actually changes.
  const [idempotencyKey, setIdempotencyKey] = useState(newKey);

  const cart = useQuery({
    queryKey: ["cart", method],
    queryFn: () => api<Cart>("/cart", { query: { shipping_method: method } }),
  });

  if (cart.isLoading) return <Spinner label="Preparing checkout" />;
  if (cart.isError) return <ErrorState message={errorMessage(cart.error)} onRetry={() => cart.refetch()} />;
  if (!cart.data || cart.data.items.length === 0) {
    return <EmptyState title="Nothing to check out" action={<Link to="/products" className="btn-primary">Browse products</Link>} />;
  }
  const summary = cart.data;
  const errors = validate(address);
  const field = (name: keyof Address) => ({
    id: name,
    value: address[name],
    onChange: (e: { target: { value: string } }) => setAddress({ ...address, [name]: e.target.value }),
    "aria-invalid": touched && !!errors[name],
    "aria-describedby": touched && errors[name] ? `${name}-error` : undefined,
    className: `input ${touched && errors[name] ? "border-danger" : ""}`,
  });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (Object.keys(errors).length > 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const order = await api<Order>("/checkout", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: { shipping_address: address, shipping_method: method, expected_total_paise: summary.total_paise },
      });
      queryClient.setQueryData(["cart"], { items: [], subtotal_paise: 0, shipping_paise: 0, total_paise: 0, item_count: 0 });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      navigate(`/orders/${order.id}?placed=1`, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Stock or price changed: show details, refresh the summary, and use a fresh key for the next attempt.
        setError(err.detail as ShortageDetail);
        setIdempotencyKey(newKey());
        cart.refetch();
      } else {
        setError(errorMessage(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1fr_360px]">
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Checkout</h1>
        <fieldset className="card p-5">
          <legend className="px-1 text-lg font-semibold">Shipping address</legend>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {([
              ["full_name", "Full name", "name", "sm:col-span-2"],
              ["line1", "Address", "street-address", "sm:col-span-2"],
              ["city", "City", "address-level2", ""],
              ["postal_code", "PIN code", "postal-code", ""],
              ["phone", "Mobile number", "tel-national", "sm:col-span-2"],
            ] as const).map(([name, label, autoComplete, span]) => (
              <div key={name} className={span}>
                <label htmlFor={name} className="label">{label}</label>
                <input {...field(name)} autoComplete={autoComplete} maxLength={name === "line1" ? 200 : 100}
                  inputMode={name === "postal_code" || name === "phone" ? "numeric" : undefined} />
                {touched && errors[name] && <p id={`${name}-error`} className="mt-1 text-xs text-danger">{errors[name]}</p>}
              </div>
            ))}
          </div>
        </fieldset>

        <fieldset className="card p-5">
          <legend className="px-1 text-lg font-semibold">Delivery speed</legend>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {METHODS.map((m) => (
              <label key={m.value} className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-sm ${
                method === m.value ? "border-brand-600 bg-brand-50" : "border-line"}`}>
                <input type="radio" name="method" value={m.value} checked={method === m.value} className="mt-1 accent-brand-600"
                  onChange={() => setMethod(m.value)} />
                <span><span className="font-medium">{SHIPPING_LABELS[m.value]}</span><br /><span className="text-muted">{m.eta}</span></span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="card p-5 text-sm">
          <h2 className="text-lg font-semibold">Payment</h2>
          <p className="mt-2 text-muted">This is a demo store: payment is simulated and no card details are collected.</p>
        </div>
      </div>

      <aside aria-label="Order summary" className="card h-fit p-5 lg:sticky lg:top-24">
        <h2 className="mb-3 text-lg font-semibold">Your order</h2>
        <ul className="mb-4 space-y-2 text-sm">
          {summary.items.map((i) => (
            <li key={i.product_id} className="flex justify-between gap-3">
              <span className="min-w-0 truncate">{i.quantity} × {i.name}</span>
              <span className="shrink-0">{formatPrice(i.line_total_paise)}</span>
            </li>
          ))}
        </ul>
        <dl className="space-y-2 border-t border-line pt-3 text-sm">
          <div className="flex justify-between"><dt className="text-muted">Subtotal</dt><dd>{formatPrice(summary.subtotal_paise)}</dd></div>
          <div className="flex justify-between"><dt className="text-muted">Shipping</dt>
            <dd>{summary.shipping_paise === 0 ? "Free" : formatPrice(summary.shipping_paise)}</dd></div>
          <div className="flex justify-between text-base font-semibold"><dt>Total</dt><dd>{formatPrice(summary.total_paise)}</dd></div>
        </dl>
        {error && (
          <div className="mt-4">
            <Alert>
              {typeof error === "string" ? error : (
                <>
                  <p className="font-medium">{error.message}</p>
                  {error.items && (
                    <ul className="mt-1 list-disc pl-5">
                      {error.items.map((i) => <li key={i.product_id}>{i.name}: {i.available} available (you asked for {i.requested})</li>)}
                    </ul>
                  )}
                  <Link to="/cart" className="mt-1 inline-block font-semibold underline">Update cart</Link>
                </>
              )}
            </Alert>
          </div>
        )}
        <button type="submit" className="btn-primary mt-5 w-full py-3" disabled={submitting || summary.items.some((i) => !i.in_stock)}>
          <Lock className="h-4 w-4" aria-hidden="true" /> {submitting ? "Placing order…" : `Place order · ${formatPrice(summary.total_paise)}`}
        </button>
      </aside>
    </form>
  );
}
