import { Heart, MapPin, ShoppingBag } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { errorMessage } from "../api/client";
import type { Product } from "../api/types";
import { useCart } from "../lib/cart";
import { useFavorites } from "../lib/favorites";
import { formatCount, formatPrice } from "../lib/format";
import { ProductImage, Stars } from "./ui";

export function ProductCard({ product }: { product: Product }) {
  const { addItem } = useCart();
  const favorites = useFavorites();
  const navigate = useNavigate();
  const [state, setState] = useState<"idle" | "adding" | "added" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const soldOut = product.stock === 0;
  const fav = favorites.isFavorite(product.id);

  async function add() {
    setState("adding");
    setError(null);
    try {
      await addItem(product.id);
      setState("added");
      setTimeout(() => setState("idle"), 1500);
    } catch (err) {
      setError(errorMessage(err));
      setState("error");
    }
  }

  return (
    <article className="card group flex w-full flex-col overflow-hidden transition-shadow hover:shadow-md" aria-labelledby={`p-${product.id}`}>
      <Link to={`/products/${product.slug}`} className="block bg-[#f1f3f4]" tabIndex={-1} aria-hidden="true">
        <ProductImage src={product.images[0]} alt="" className="transition-transform group-hover:scale-[1.03]" />
      </Link>
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 id={`p-${product.id}`} className="line-clamp-2 font-semibold leading-snug">
            <Link to={`/products/${product.slug}`} className="hover:text-brand-700">
              {product.name}
            </Link>
          </h3>
          <button
            type="button"
            className="shrink-0 rounded-full p-1 hover:bg-brand-50"
            aria-pressed={fav}
            aria-label={fav ? `Remove ${product.name} from favorites` : `Add ${product.name} to favorites`}
            onClick={() => (favorites.enabled ? favorites.toggle(product.id) : navigate("/login?next=/products"))}
          >
            <Heart className={`h-5 w-5 ${fav ? "fill-danger text-danger" : "text-ink"}`} aria-hidden="true" />
          </button>
        </div>
        <Stars rating={product.rating} count={product.review_count} />
        <p className="flex items-center gap-1 text-xs text-muted">
          <MapPin className="h-3 w-3" aria-hidden="true" /> {product.location}
        </p>
        <div className="mt-auto pt-2">
          <p className="text-xl font-bold">{formatPrice(product.price_paise)}</p>
          <p className="text-xs text-muted">
            {formatCount(product.sold_count)} Sold
            {product.stock > 0 && product.stock < 5 && <span className="ml-2 font-medium text-orange-600">Only {product.stock} left</span>}
          </p>
        </div>
        <button type="button" className="btn-primary mt-2 w-full" onClick={add} disabled={soldOut || state === "adding"}>
          <ShoppingBag className="h-4 w-4" aria-hidden="true" />
          {soldOut ? "Sold out" : state === "adding" ? "Adding…" : state === "added" ? "Added ✓" : "Add to Cart"}
        </button>
        {error && <p role="alert" className="text-xs text-danger">{error}</p>}
      </div>
    </article>
  );
}

export function ProductCardSkeleton() {
  return (
    <div className="card w-full overflow-hidden" aria-hidden="true">
      <div className="aspect-[4/3] animate-pulse bg-line/60" />
      <div className="space-y-2 p-4">
        <div className="h-4 w-3/4 animate-pulse rounded bg-line" />
        <div className="h-3 w-1/2 animate-pulse rounded bg-line" />
        <div className="h-6 w-1/3 animate-pulse rounded bg-line" />
        <div className="h-9 animate-pulse rounded-lg bg-line" />
      </div>
    </div>
  );
}
