import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, errorMessage } from "../api/client";
import type { Product } from "../api/types";
import { ProductCard } from "../components/ProductCard";
import { EmptyState, ErrorState, Spinner } from "../components/ui";
import { useFavorites } from "../lib/favorites";

export function FavoritesPage() {
  const { ids } = useFavorites();
  const list = [...ids];
  const products = useQuery({
    queryKey: ["products-by-ids", list],
    queryFn: () => api<Product[]>("/products/by-ids", { query: { ids: list } }),
    enabled: list.length > 0,
  });
  if (list.length === 0) {
    return <EmptyState title="No favorites yet" action={<Link to="/products" className="btn-primary">Discover products</Link>}>
      Tap the heart on any product to save it here.
    </EmptyState>;
  }
  if (products.isLoading) return <Spinner label="Loading favorites" />;
  if (products.isError) return <ErrorState message={errorMessage(products.error)} onRetry={() => products.refetch()} />;
  return (
    <section aria-labelledby="fav-heading">
      <h1 id="fav-heading" className="mb-4 text-2xl font-semibold">Favorites</h1>
      <ul className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {products.data?.map((p) => <li key={p.id} className="flex"><ProductCard product={p} /></li>)}
      </ul>
    </section>
  );
}

export function NotFoundPage() {
  return <EmptyState title="Page not found" action={<Link to="/products" className="btn-primary">Go to the store</Link>}>
    The page you were looking for doesn’t exist.
  </EmptyState>;
}
