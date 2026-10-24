import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Heart, MapPin, ShieldCheck, ShoppingBag, Truck } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ApiError, api, errorMessage } from "../api/client";
import type { Product } from "../api/types";
import { Alert, EmptyState, ErrorState, ProductImage, QuantityStepper, Spinner, Stars } from "../components/ui";
import { MAX_QTY, useCart } from "../lib/cart";
import { useFavorites } from "../lib/favorites";
import { formatCount, formatPrice, SHIPPING_LABELS } from "../lib/format";

export function ProductDetailPage() {
  const { slug = "" } = useParams();
  const product = useQuery({
    queryKey: ["product", slug],
    queryFn: () => api<Product>(`/products/${encodeURIComponent(slug)}`),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });
  if (product.isLoading) return <Spinner label="Loading product" />;
  if (product.isError) {
    if (product.error instanceof ApiError && product.error.status === 404) {
      return <EmptyState title="Product not found" action={<Link to="/products" className="btn-primary">Back to products</Link>}>
        It may have been removed or the link is incorrect.
      </EmptyState>;
    }
    return <ErrorState message={errorMessage(product.error)} onRetry={() => product.refetch()} />;
  }
  return product.data ? <ProductDetail product={product.data} /> : null;
}

function ProductDetail({ product }: { product: Product }) {
  const { addItem } = useCart();
  const favorites = useFavorites();
  const navigate = useNavigate();
  const [qty, setQty] = useState(1);
  const [image, setImage] = useState(0);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const maxQty = Math.min(MAX_QTY, product.stock);
  const fav = favorites.isFavorite(product.id);

  async function add() {
    setBusy(true);
    setMessage(null);
    try {
      await addItem(product.id, qty);
      setMessage({ kind: "success", text: `Added ${qty} × ${product.name} to your cart.` });
    } catch (err) {
      setMessage({ kind: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="mx-auto max-w-6xl">
      <Link to="/products" className="mb-4 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> All products
      </Link>
      <div className="grid gap-8 md:grid-cols-2">
        <div>
          <div className="card overflow-hidden bg-[#f1f3f4]">
            <ProductImage src={product.images[image]} alt={product.name} />
          </div>
          {product.images.length > 1 && (
            <div className="mt-3 flex gap-3" role="group" aria-label="Product images">
              {product.images.map((src, i) => (
                <button key={src} type="button" aria-label={`Show image ${i + 1}`} aria-pressed={i === image}
                  onClick={() => setImage(i)}
                  className={`card w-20 overflow-hidden bg-[#f1f3f4] ${i === image ? "ring-2 ring-brand-500" : ""}`}>
                  <ProductImage src={src} alt="" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <div>
            <p className="text-sm font-medium text-brand-700">{product.brand} · {product.category}</p>
            <h1 className="mt-1 text-3xl font-semibold">{product.name}</h1>
          </div>
          <Stars rating={product.rating} count={product.review_count} />
          <p className="text-3xl font-bold">{formatPrice(product.price_paise)}</p>
          <p className="text-sm text-muted">{formatCount(product.sold_count)} sold · SKU {product.sku}</p>
          <p className="leading-relaxed">{product.description}</p>

          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div className="card p-3">
              <dt className="flex items-center gap-1 text-muted"><MapPin className="h-4 w-4" aria-hidden="true" /> Ships from</dt>
              <dd className="font-medium">{product.location}</dd>
            </div>
            <div className="card p-3">
              <dt className="flex items-center gap-1 text-muted"><Truck className="h-4 w-4" aria-hidden="true" /> Delivery</dt>
              <dd className="font-medium">{product.shipping.map((s) => SHIPPING_LABELS[s]).join(", ")}</dd>
            </div>
          </dl>
          {product.colors.length > 0 && (
            <p className="text-sm"><span className="text-muted">Colours:</span> <span className="capitalize">{product.colors.join(", ")}</span></p>
          )}

          <p className={`text-sm font-medium ${product.stock === 0 ? "text-danger" : product.stock < 5 ? "text-orange-600" : "text-brand-700"}`}>
            {product.stock === 0 ? "Out of stock" : product.stock < 5 ? `Only ${product.stock} left in stock` : "In stock"}
          </p>

          {product.stock > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              <QuantityStepper value={qty} max={maxQty} onChange={setQty} label="Quantity" />
              <button type="button" className="btn-primary flex-1 py-3" onClick={add} disabled={busy}>
                <ShoppingBag className="h-4 w-4" aria-hidden="true" /> {busy ? "Adding…" : "Add to Cart"}
              </button>
              <button type="button" className="btn-outline py-3" aria-pressed={fav}
                aria-label={fav ? "Remove from favorites" : "Add to favorites"}
                onClick={() => (favorites.enabled ? favorites.toggle(product.id) : navigate(`/login?next=/products/${product.slug}`))}>
                <Heart className={`h-5 w-5 ${fav ? "fill-danger text-danger" : ""}`} aria-hidden="true" />
              </button>
            </div>
          )}
          {message && (
            <Alert kind={message.kind}>
              {message.text}{" "}
              {message.kind === "success" && <Link to="/cart" className="font-semibold underline">View cart</Link>}
            </Alert>
          )}
          <p className="flex items-center gap-2 text-xs text-muted">
            <ShieldCheck className="h-4 w-4 text-brand-600" aria-hidden="true" />
            Simulated checkout — no real payment is taken. 7-day returns.
          </p>
        </div>
      </div>
    </article>
  );
}
