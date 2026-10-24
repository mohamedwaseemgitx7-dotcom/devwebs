/**
 * Cart state. Signed-in users use the server cart (/api/v1/cart). Guests keep {product_id, quantity} pairs in
 * localStorage; their display prices come from the catalog and are re-validated by the server at checkout.
 * On login the guest cart is merged into the server cart and cleared locally.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { Cart, Product } from "../api/types";
import { useAuth } from "./auth";

const GUEST_KEY = "fc_guest_cart";
export const MAX_QTY = 10;
const FREE_SHIPPING_PAISE = 99_900;
const REGULAR_FEE_PAISE = 4_900;

interface GuestLine {
  product_id: string;
  quantity: number;
}

function readGuest(): GuestLine[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(GUEST_KEY) ?? "[]") as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((l): l is GuestLine => /^[0-9a-f]{24}$/.test(l?.product_id) && Number.isInteger(l?.quantity))
      .map((l) => ({ product_id: l.product_id, quantity: Math.min(MAX_QTY, Math.max(1, l.quantity)) }))
      .slice(0, 50);
  } catch {
    return [];
  }
}

function writeGuest(lines: GuestLine[]) {
  try {
    localStorage.setItem(GUEST_KEY, JSON.stringify(lines));
  } catch {
    /* storage full or blocked: cart still works for this page view */
  }
}

interface CartContextValue {
  cart: Cart | undefined;
  isLoading: boolean;
  setQuantity: (productId: string, quantity: number) => Promise<void>;
  addItem: (productId: string, quantity?: number) => Promise<void>;
  removeItem: (productId: string) => Promise<void>;
  isGuest: boolean;
}

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const queryClient = useQueryClient();
  const isGuest = status !== "authenticated";
  const [guestLines, setGuestLines] = useState<GuestLine[]>(readGuest);

  // Merge the guest cart into the server cart right after sign-in.
  // Take-and-clear BEFORE the request: the merge endpoint adds quantities, so each guest cart must be sent at most
  // once. Clearing only on success doubled quantities when a reload/navigation aborted the response after the
  // server had already applied it (TROUBLESHOOTING TS-007). On an error response the lines are restored.
  useEffect(() => {
    if (status !== "authenticated") return;
    const lines = readGuest();
    if (!lines.length) return;
    writeGuest([]); // synchronous: this is what prevents a second merge of the same lines
    api<Cart>("/cart/merge", { method: "POST", body: { items: lines } })
      .then((cart) => {
        queryClient.setQueryData(["cart"], cart);
        setGuestLines([]);
      })
      .catch(() => {
        writeGuest(lines);
        setGuestLines(lines);
      });
  }, [status, queryClient]);

  const serverCart = useQuery({
    queryKey: ["cart"],
    queryFn: () => api<Cart>("/cart"),
    enabled: status === "authenticated",
  });

  const guestIds = guestLines.map((l) => l.product_id);
  const guestProducts = useQuery({
    queryKey: ["products-by-ids", guestIds],
    queryFn: () => api<Product[]>("/products/by-ids", { query: { ids: guestIds } }),
    enabled: isGuest && guestIds.length > 0,
  });

  const guestCart: Cart = useMemo(() => {
    const byId = new Map((guestProducts.data ?? []).map((p) => [p.id, p]));
    const items = guestLines.flatMap((l) => {
      const p = byId.get(l.product_id);
      if (!p) return [];
      return [{
        product_id: p.id,
        name: p.name,
        image: p.images[0] ?? null,
        unit_price_paise: p.price_paise,
        quantity: l.quantity,
        line_total_paise: p.price_paise * l.quantity,
        in_stock: p.stock >= l.quantity,
        available: p.stock,
      }];
    });
    const subtotal = items.reduce((s, i) => s + i.line_total_paise, 0);
    const shipping = subtotal === 0 || subtotal >= FREE_SHIPPING_PAISE ? 0 : REGULAR_FEE_PAISE;
    return {
      items,
      subtotal_paise: subtotal,
      shipping_paise: shipping,
      total_paise: subtotal + shipping,
      item_count: items.reduce((s, i) => s + i.quantity, 0),
    };
  }, [guestLines, guestProducts.data]);

  const setServerQty = useMutation({
    mutationFn: ({ productId, quantity }: { productId: string; quantity: number }) =>
      quantity > 0
        ? api<Cart>("/cart/items", { method: "PUT", body: { product_id: productId, quantity } })
        : api<Cart>(`/cart/items/${productId}`, { method: "DELETE" }),
    onSuccess: (cart) => queryClient.setQueryData(["cart"], cart),
  });

  const setQuantity = useCallback(
    async (productId: string, quantity: number) => {
      const qty = Math.min(MAX_QTY, Math.max(0, quantity));
      if (!isGuest) {
        await setServerQty.mutateAsync({ productId, quantity: qty });
        return;
      }
      setGuestLines((prev) => {
        const rest = prev.filter((l) => l.product_id !== productId);
        const next = qty > 0 ? [...rest, { product_id: productId, quantity: qty }] : rest;
        writeGuest(next);
        return next;
      });
    },
    [isGuest, setServerQty],
  );

  const currentCart = isGuest ? guestCart : serverCart.data;

  const addItem = useCallback(
    async (productId: string, quantity = 1) => {
      const existing = currentCart?.items.find((i) => i.product_id === productId)?.quantity ?? 0;
      await setQuantity(productId, existing + quantity);
    },
    [currentCart, setQuantity],
  );

  const removeItem = useCallback((productId: string) => setQuantity(productId, 0), [setQuantity]);

  const value = useMemo(
    () => ({
      cart: currentCart,
      isLoading: isGuest ? guestProducts.isLoading && guestIds.length > 0 : serverCart.isLoading,
      setQuantity,
      addItem,
      removeItem,
      isGuest,
    }),
    [currentCart, isGuest, guestProducts.isLoading, guestIds.length, serverCart.isLoading, setQuantity, addItem,
     removeItem],
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside <CartProvider>");
  return ctx;
}
