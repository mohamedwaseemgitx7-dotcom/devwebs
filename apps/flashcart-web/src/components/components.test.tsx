import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode, StrictMode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Product } from "../api/types";
import { CartProvider, useCart } from "../lib/cart";
import { ProductCard } from "./ProductCard";
import { QuantityStepper, Stars } from "./ui";

const authState = { status: "anonymous" as "anonymous" | "authenticated" | "loading", user: null };
vi.mock("../lib/auth", () => ({ useAuth: () => authState }));

const PRODUCT: Product = {
  id: "6adc9ddd94809982ce0f5ba3", sku: "FC-ELE-0001", slug: "test-mouse-fc-ele-0001", name: "Test Mouse", brand: "Swiftpoint",
  category: "Electronics", description: "A mouse", price_paise: 269900, currency: "INR", images: ["/products/mouse-black.svg"],
  colors: ["black"], shipping: ["regular"], rating: 4.4, review_count: 10, sold_count: 135, stock: 3, location: "Chennai",
  version: 1, active: true,
};

type FetchMock = ReturnType<typeof vi.fn>;
let fetchMock: FetchMock;

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter><CartProvider>{children}</CartProvider></MemoryRouter>
    </QueryClientProvider>
  );
}

// StrictMode must wrap the PROVIDERS (where the merge effect lives) so React double-invokes their effects.
function strictWrapper({ children }: { children: ReactNode }) {
  return <StrictMode>{wrapper({ children })}</StrictMode>;
}

beforeEach(() => {
  authState.status = "anonymous";
  fetchMock = vi.fn((url: string) => {
    if (url.startsWith("/api/v1/products/by-ids")) return json([PRODUCT]);
    if (url.startsWith("/api/v1/cart/merge")) return json({ items: [], subtotal_paise: 0, shipping_paise: 0, total_paise: 0, item_count: 0 });
    if (url.startsWith("/api/v1/cart")) return json({ items: [], subtotal_paise: 0, shipping_paise: 0, total_paise: 0, item_count: 0 });
    return json({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("ProductCard", () => {
  it("shows price, rating, low-stock warning and accessible actions", () => {
    render(<ProductCard product={PRODUCT} />, { wrapper });
    expect(screen.getByRole("heading", { name: "Test Mouse" })).toBeInTheDocument();
    expect(screen.getByText("₹2,699")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Rated 4.4 out of 5" })).toBeInTheDocument();
    expect(screen.getByText("Only 3 left")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Test Mouse to favorites" })).toHaveAttribute("aria-pressed", "false");
  });

  it("disables add-to-cart when sold out", () => {
    render(<ProductCard product={{ ...PRODUCT, stock: 0 }} />, { wrapper });
    expect(screen.getByRole("button", { name: /Sold out/ })).toBeDisabled();
  });

  it("adds to the guest cart", async () => {
    function Count() {
      const { cart } = useCart();
      return <p>count:{cart?.item_count ?? 0}</p>;
    }
    render(<><ProductCard product={PRODUCT} /><Count /></>, { wrapper });
    await userEvent.click(screen.getByRole("button", { name: /Add to Cart/ }));
    await waitFor(() => expect(screen.getByText("count:1")).toBeInTheDocument());
    expect(JSON.parse(localStorage.getItem("fc_guest_cart")!)).toEqual([{ product_id: PRODUCT.id, quantity: 1 }]);
  });
});

const merges = () => fetchMock.mock.calls.filter(([u]) => String(u).startsWith("/api/v1/cart/merge"));

describe("CartProvider guest-cart merge (regression TS-007)", () => {
  it("does not merge twice when the page reloads before the merge response arrives", async () => {
    // Reproduces the e2e failure: the server applied the merge, but a navigation/reload aborted the response,
    // so the old code (which cleared localStorage only on success) merged the same lines again → doubled qty.
    localStorage.setItem("fc_guest_cart", JSON.stringify([{ product_id: PRODUCT.id, quantity: 2 }]));
    fetchMock.mockImplementation((url: string) =>
      url.startsWith("/api/v1/cart/merge")
        ? new Promise<Response>(() => undefined) // response never arrives (aborted by reload)
        : json({ items: [], subtotal_paise: 0, shipping_paise: 0, total_paise: 0, item_count: 0 }));
    authState.status = "authenticated";
    const first = render(<p>signed in</p>, { wrapper: strictWrapper });
    await waitFor(() => expect(merges()).toHaveLength(1));
    first.unmount(); // page reload
    render(<p>signed in again</p>, { wrapper: strictWrapper });
    await screen.findByText("signed in again");
    await new Promise((r) => setTimeout(r, 50));
    expect(merges()).toHaveLength(1);
    expect(JSON.parse(localStorage.getItem("fc_guest_cart")!)).toEqual([]);
  });

  it("restores the guest cart if the merge request fails", async () => {
    localStorage.setItem("fc_guest_cart", JSON.stringify([{ product_id: PRODUCT.id, quantity: 2 }]));
    fetchMock.mockImplementation((url: string) =>
      url.startsWith("/api/v1/cart/merge") ? json({ detail: "boom" }, 500) : json({ items: [], subtotal_paise: 0, shipping_paise: 0, total_paise: 0, item_count: 0 }));
    authState.status = "authenticated";
    render(<p>signed in</p>, { wrapper });
    await waitFor(() => expect(JSON.parse(localStorage.getItem("fc_guest_cart")!)).toEqual([{ product_id: PRODUCT.id, quantity: 2 }]));
  });
});

describe("ui primitives", () => {
  it("QuantityStepper respects bounds", async () => {
    const onChange = vi.fn();
    render(<QuantityStepper value={1} max={2} onChange={onChange} label="Qty" />);
    expect(screen.getByRole("button", { name: "Decrease quantity" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Increase quantity" }));
    expect(onChange).toHaveBeenCalledWith(2);
  });

  it("Stars exposes an accessible rating", () => {
    render(<Stars rating={3.6} count={1} />);
    expect(screen.getByRole("img", { name: "Rated 3.6 out of 5" })).toBeInTheDocument();
    expect(screen.getByText("1 Review")).toBeInTheDocument();
  });
});
