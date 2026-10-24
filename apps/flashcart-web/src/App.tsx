import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router";
import { Layout, RequireAuth } from "./components/Layout";
import { Spinner } from "./components/ui";
import { LoginPage, SignupPage } from "./pages/AuthPages";
import { CartPage } from "./pages/CartPage";
import { FavoritesPage, NotFoundPage } from "./pages/FavoritesPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { ProductsPage } from "./pages/ProductsPage";

// Code-split the less-visited routes so the storefront loads faster.
const CheckoutPage = lazy(() => import("./pages/CheckoutPage").then((m) => ({ default: m.CheckoutPage })));
const OrdersPage = lazy(() => import("./pages/OrdersPage").then((m) => ({ default: m.OrdersPage })));
const OrderDetailPage = lazy(() => import("./pages/OrdersPage").then((m) => ({ default: m.OrderDetailPage })));
const AdminDashboard = lazy(() => import("./pages/admin/AdminPages").then((m) => ({ default: m.AdminDashboard })));
const AdminProducts = lazy(() => import("./pages/admin/AdminPages").then((m) => ({ default: m.AdminProducts })));
const AdminOrders = lazy(() => import("./pages/admin/AdminPages").then((m) => ({ default: m.AdminOrders })));

export function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/products" replace />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="products/:slug" element={<ProductDetailPage />} />
          <Route path="cart" element={<CartPage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="signup" element={<SignupPage />} />
          <Route path="checkout" element={<RequireAuth><CheckoutPage /></RequireAuth>} />
          <Route path="orders" element={<RequireAuth><OrdersPage /></RequireAuth>} />
          <Route path="orders/:id" element={<RequireAuth><OrderDetailPage /></RequireAuth>} />
          <Route path="favorites" element={<RequireAuth><FavoritesPage /></RequireAuth>} />
          <Route path="admin" element={<RequireAuth admin><AdminDashboard /></RequireAuth>} />
          <Route path="admin/products" element={<RequireAuth admin><AdminProducts /></RequireAuth>} />
          <Route path="admin/orders" element={<RequireAuth admin><AdminOrders /></RequireAuth>} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
