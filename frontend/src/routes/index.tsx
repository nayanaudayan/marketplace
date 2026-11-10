import { Navigate, Route, Routes } from "react-router-dom";
import MainLayout from "@/layouts/MainLayout";
import AdminLayout from "@/layouts/AdminLayout";
import { IS_ADMIN_APP } from "@/config";
import ProtectedRoute from "./ProtectedRoute";
import HomePage from "@/pages/HomePage";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import AISearchPage from "@/pages/AISearchPage";
import CatalogPage from "@/pages/CatalogPage";
import ProductDetailPage from "@/pages/ProductDetailPage";
import CartPage from "@/pages/CartPage";
import CheckoutPage from "@/pages/CheckoutPage";
import OrdersPage from "@/pages/OrdersPage";
import OrderDetailPage from "@/pages/OrderDetailPage";
import WishlistPage from "@/pages/WishlistPage";
import SellerDashboardPage from "@/pages/SellerDashboardPage";
import AdminDashboardPage from "@/pages/admin/AdminDashboardPage";
import AdminSellersPage from "@/pages/admin/AdminSellersPage";
import AdminOrdersPage from "@/pages/admin/AdminOrdersPage";
import AdminCategoriesPage from "@/pages/admin/AdminCategoriesPage";
import AdminAuthLayout from "@/layouts/AdminAuthLayout";
import NotFoundPage from "@/pages/NotFoundPage";

/** Customers and sellers. There is deliberately no admin route here: admins use the separate admin app. */
function StorefrontRoutes() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<HomePage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="search" element={<AISearchPage />} />
        <Route path="products" element={<CatalogPage />} />
        <Route path="products/:id" element={<ProductDetailPage />} />

        <Route element={<ProtectedRoute roles={["customer"]} />}>
          <Route path="cart" element={<CartPage />} />
          <Route path="checkout" element={<CheckoutPage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="orders/:id" element={<OrderDetailPage />} />
          <Route path="wishlist" element={<WishlistPage />} />
        </Route>

        <Route element={<ProtectedRoute roles={["seller"]} />}>
          <Route path="seller" element={<SellerDashboardPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

/** Administrators only: sign-in plus a sidebar console. No shop pages exist in this build. */
function AdminRoutes() {
  return (
    <Routes>
      <Route element={<AdminAuthLayout />}>
        <Route path="login" element={<LoginPage />} />
      </Route>
      <Route element={<ProtectedRoute roles={["admin"]} fallback="/login" />}>
        <Route element={<AdminLayout />}>
          <Route index element={<AdminDashboardPage />} />
          <Route path="sellers" element={<AdminSellersPage />} />
          <Route path="orders" element={<AdminOrdersPage />} />
          <Route path="categories" element={<AdminCategoriesPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function AppRoutes() {
  return IS_ADMIN_APP ? <AdminRoutes /> : <StorefrontRoutes />;
}
