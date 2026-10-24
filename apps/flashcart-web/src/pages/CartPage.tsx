import { AlertTriangle, ShoppingBag, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { errorMessage } from "../api/client";
import { Alert, EmptyState, ProductImage, QuantityStepper, Spinner } from "../components/ui";
import { useAuth } from "../lib/auth";
import { MAX_QTY, useCart } from "../lib/cart";
import { formatPrice } from "../lib/format";

export function CartPage() {
  const { cart, isLoading, setQuantity, removeItem, isGuest } = useCart();
  const { status } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  if (status === "loading" || isLoading) return <Spinner label="Loading your cart" />;
  if (!cart || cart.items.length === 0) {
    return (
      <EmptyState title="Your cart is empty" action={<Link to="/products" className="btn-primary">Start shopping</Link>}>
        Browse products and add something you like.
      </EmptyState>
    );
  }

  const blocked = cart.items.some((i) => !i.in_stock);

  async function run(action: () => Promise<void>) {
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1fr_340px]">
      <section aria-labelledby="cart-heading">
        <h1 id="cart-heading" className="mb-4 text-2xl font-semibold">Shopping cart</h1>
        {error && <div className="mb-3"><Alert>{error}</Alert></div>}
        <ul className="card divide-y divide-line">
          {cart.items.map((line) => (
            <li key={line.product_id} className="flex gap-4 p-4">
              <div className="w-24 shrink-0 overflow-hidden rounded-lg bg-[#f1f3f4]">
                <ProductImage src={line.image} alt="" />
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-2">
                <div className="flex justify-between gap-3">
                  <h2 className="font-medium">{line.name}</h2>
                  <p className="font-semibold">{formatPrice(line.line_total_paise)}</p>
                </div>
                <p className="text-sm text-muted">{formatPrice(line.unit_price_paise)} each</p>
                {!line.in_stock && (
                  <p className="flex items-center gap-1 text-sm text-danger">
                    <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                    {line.available === 0 ? "Out of stock — remove to continue" : `Only ${line.available} available — reduce quantity`}
                  </p>
                )}
                <div className="flex items-center gap-3">
                  <QuantityStepper value={line.quantity} max={Math.min(MAX_QTY, Math.max(line.available, 1))}
                    label={`Quantity for ${line.name}`} onChange={(q) => run(() => setQuantity(line.product_id, q))} />
                  <button type="button" className="btn-ghost text-danger" onClick={() => run(() => removeItem(line.product_id))}
                    aria-label={`Remove ${line.name} from cart`}>
                    <Trash2 className="h-4 w-4" aria-hidden="true" /> Remove
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <aside aria-label="Order summary" className="card h-fit p-5 lg:sticky lg:top-24">
        <h2 className="mb-4 text-lg font-semibold">Order summary</h2>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between"><dt className="text-muted">Items ({cart.item_count})</dt><dd>{formatPrice(cart.subtotal_paise)}</dd></div>
          <div className="flex justify-between"><dt className="text-muted">Shipping (regular)</dt>
            <dd>{cart.shipping_paise === 0 ? "Free" : formatPrice(cart.shipping_paise)}</dd></div>
          <div className="flex justify-between border-t border-line pt-2 text-base font-semibold"><dt>Total</dt><dd>{formatPrice(cart.total_paise)}</dd></div>
        </dl>
        {cart.subtotal_paise < 99_900 && (
          <p className="mt-3 text-xs text-muted">Add {formatPrice(99_900 - cart.subtotal_paise)} more for free regular shipping.</p>
        )}
        <button type="button" className="btn-primary mt-5 w-full py-3" disabled={blocked}
          onClick={() => navigate(isGuest ? "/login?next=/checkout" : "/checkout")}>
          <ShoppingBag className="h-4 w-4" aria-hidden="true" /> {isGuest ? "Sign in to check out" : "Proceed to checkout"}
        </button>
        {blocked && <p className="mt-2 text-xs text-danger">Fix the highlighted items to continue.</p>}
        {isGuest && <p className="mt-2 text-xs text-muted">Your cart is saved on this device and moves to your account when you sign in.</p>}
      </aside>
    </div>
  );
}
