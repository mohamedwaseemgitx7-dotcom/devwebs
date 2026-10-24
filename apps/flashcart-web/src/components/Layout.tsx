import { ClipboardList, Heart, LayoutDashboard, LogIn, LogOut, Package, Search, ShoppingBag, Store, User, Zap } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router";
import { useAuth } from "../lib/auth";
import { useCart } from "../lib/cart";

function RailLink({ to, label, icon }: { to: string; label: string; icon: ReactNode }) {
  return (
    <NavLink to={to} title={label} aria-label={label}
      className={({ isActive }) => `flex h-11 w-11 items-center justify-center rounded-xl transition-colors ${
        isActive ? "bg-brand-50 text-brand-700" : "text-muted hover:bg-canvas hover:text-ink"}`}>
      {icon}
    </NavLink>
  );
}

const CRUMBS: Record<string, string> = {
  products: "Products", cart: "Cart", checkout: "Checkout", orders: "Orders", favorites: "Favorites",
  admin: "Admin", login: "Sign in", signup: "Create account",
};

export function Layout() {
  const { user, logout } = useAuth();
  const { cart } = useCart();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const urlQuery = params.get("q") ?? "";
  const [query, setQuery] = useState(urlQuery);
  const [syncedQuery, setSyncedQuery] = useState(urlQuery);
  const searchRef = useRef<HTMLInputElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPath, setMenuPath] = useState(location.pathname);
  const section = location.pathname.split("/")[1] || "products";

  // Keep the search box in sync with the URL, and close the user menu on navigation. Adjusting state during
  // render (instead of in an effect) avoids an extra render pass: https://react.dev/learn/you-might-not-need-an-effect
  if (urlQuery !== syncedQuery) {
    setSyncedQuery(urlQuery);
    setQuery(urlQuery);
  }
  if (location.pathname !== menuPath) {
    setMenuPath(location.pathname);
    setMenuOpen(false);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function submitSearch(e: FormEvent) {
    e.preventDefault();
    const q = query.trim().slice(0, 100);
    navigate(q ? `/products?q=${encodeURIComponent(q)}` : "/products");
  }

  return (
    <div className="flex min-h-dvh">
      <a href="#main" className="sr-only z-50 rounded bg-white p-2 focus:not-sr-only focus:fixed focus:left-2 focus:top-2">
        Skip to content
      </a>
      <nav aria-label="Main" className="sticky top-0 hidden h-dvh w-20 shrink-0 flex-col items-center gap-2 border-r border-line bg-white py-5 md:flex">
        <Link to="/products" aria-label="FlashCart home" className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-brand-600 text-white">
          <Zap className="h-6 w-6 fill-white" aria-hidden="true" />
        </Link>
        <RailLink to="/products" label="Products" icon={<Store className="h-5 w-5" />} />
        <RailLink to="/favorites" label="Favorites" icon={<Heart className="h-5 w-5" />} />
        <RailLink to="/cart" label="Cart" icon={<ShoppingBag className="h-5 w-5" />} />
        <RailLink to="/orders" label="My orders" icon={<ClipboardList className="h-5 w-5" />} />
        {user?.role === "admin" && (
          <>
            <div className="my-2 h-px w-10 bg-line" />
            <RailLink to="/admin" label="Admin dashboard" icon={<LayoutDashboard className="h-5 w-5" />} />
            <RailLink to="/admin/products" label="Manage products" icon={<Package className="h-5 w-5" />} />
          </>
        )}
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur">
          <div className="flex items-center gap-3 px-4 py-3 md:px-8">
            <Link to="/products" className="flex items-center gap-2 font-bold text-brand-700 md:hidden" aria-label="FlashCart home">
              <Zap className="h-5 w-5 fill-brand-600" aria-hidden="true" /> FlashCart
            </Link>
            <nav aria-label="Breadcrumb" className="hidden text-sm text-muted lg:block">
              <ol className="flex items-center gap-2">
                <li><Link to="/products" className="hover:text-ink">FlashCart Store</Link></li>
                <li aria-hidden="true">›</li>
                <li aria-current="page" className="font-medium text-ink">{CRUMBS[section] ?? "Page"}</li>
              </ol>
            </nav>
            <form role="search" onSubmit={submitSearch} className="mx-auto w-full max-w-xl">
              <label htmlFor="site-search" className="sr-only">Search products</label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
                <input id="site-search" ref={searchRef} type="search" value={query} maxLength={100}
                  onChange={(e) => setQuery(e.target.value)} placeholder="Search products…"
                  className="input rounded-xl bg-canvas py-2.5 pl-9 pr-16" />
                <kbd className="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 rounded border border-line bg-white px-1.5 text-[10px] text-muted sm:block">
                  Ctrl K
                </kbd>
              </div>
            </form>
            <Link to="/cart" className="relative rounded-xl border border-line p-2.5 hover:bg-brand-50"
              aria-label={`Cart, ${cart?.item_count ?? 0} items`}>
              <ShoppingBag className="h-5 w-5" aria-hidden="true" />
              {(cart?.item_count ?? 0) > 0 && (
                <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-600 px-1 text-[11px] font-semibold text-white">
                  {cart?.item_count}
                </span>
              )}
            </Link>
            {user ? (
              <div className="relative">
                <button type="button" className="flex items-center gap-2 rounded-xl border border-line p-2.5 hover:bg-brand-50"
                  aria-haspopup="menu" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>
                  <User className="h-5 w-5" aria-hidden="true" />
                  <span className="hidden max-w-28 truncate text-sm sm:inline">{user.name}</span>
                </button>
                {menuOpen && (
                  <div role="menu" className="card absolute right-0 mt-2 w-56 p-1 shadow-lg">
                    <p className="truncate px-3 py-2 text-xs text-muted">{user.email}</p>
                    <Link role="menuitem" to="/orders" className="block rounded-lg px-3 py-2 text-sm hover:bg-canvas">My orders</Link>
                    <Link role="menuitem" to="/favorites" className="block rounded-lg px-3 py-2 text-sm hover:bg-canvas">Favorites</Link>
                    {user.role === "admin" && (
                      <Link role="menuitem" to="/admin" className="block rounded-lg px-3 py-2 text-sm hover:bg-canvas">Admin dashboard</Link>
                    )}
                    <button role="menuitem" type="button" className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-canvas"
                      onClick={async () => { await logout(); navigate("/products"); }}>
                      <LogOut className="h-4 w-4" aria-hidden="true" /> Sign out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <Link to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} className="btn-primary">
                <LogIn className="h-4 w-4" aria-hidden="true" /> <span className="hidden sm:inline">Sign in</span>
              </Link>
            )}
          </div>
        </header>
        <main id="main" tabIndex={-1} className="flex-1 px-4 py-6 md:px-8">
          <Outlet />
        </main>
        <nav aria-label="Mobile" className="sticky bottom-0 grid grid-cols-4 border-t border-line bg-white md:hidden">
          {[["/products", "Shop", Store], ["/favorites", "Saved", Heart], ["/cart", "Cart", ShoppingBag], ["/orders", "Orders", ClipboardList]].map(
            ([to, label, Icon]) => {
              const I = Icon as typeof Store;
              return (
                <NavLink key={to as string} to={to as string}
                  className={({ isActive }) => `flex flex-col items-center gap-0.5 py-2 text-[11px] ${isActive ? "text-brand-700" : "text-muted"}`}>
                  <I className="h-5 w-5" aria-hidden="true" /> {label as string}
                </NavLink>
              );
            })}
        </nav>
      </div>
    </div>
  );
}

export function RequireAuth({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const { user, status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <p role="status" className="py-16 text-center text-muted">Checking your session…</p>;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (admin && user.role !== "admin") {
    return (
      <div className="card mx-auto max-w-md p-8 text-center">
        <h1 className="text-lg font-semibold">Admins only</h1>
        <p className="mt-2 text-sm text-muted">Your account does not have access to this page.</p>
      </div>
    );
  }
  return <>{children}</>;
}
