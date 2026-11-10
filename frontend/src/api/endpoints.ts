import { api, request } from "./client";
import type {
  AICompareResponse, AIFilters, AISearchResponse, AdminDashboard, Address, AuthResponse, Cart, Category,
  Order, PaymentInit, ProductCard, ProductDetail, ProductInput, ProductList, Review, Seller, SellerOrderItem, User,
} from "@/types";

export const authApi = {
  register: (b: { name: string; email: string; password: string; phone?: string; role: "customer" | "seller" }) =>
    api.post<AuthResponse>("/auth/register", b, false),
  login: (b: { email: string; password: string }) => api.post<AuthResponse>("/auth/login", b, false),
  logout: (refresh_token: string) => api.post<void>("/auth/logout", { refresh_token }),
  me: () => api.get<User>("/auth/me"),
};

export const userApi = {
  addresses: () => api.get<Address[]>("/users/addresses"),
  addAddress: (b: Omit<Address, "id" | "is_default"> & { is_default?: boolean }) =>
    api.post<Address>("/users/addresses", b),
};

export const categoryApi = {
  list: () => api.get<Category[]>("/categories"),
};

export interface ProductQuery {
  q?: string;
  category_id?: number;
  brand?: string;
  min_price?: number;
  max_price?: number;
  in_stock?: boolean;
  sort_by?: string;
  page?: number;
  page_size?: number;
}

export const productApi = {
  list: (q: ProductQuery) => api.get<ProductList>("/products", q as Record<string, string | number | boolean>),
  get: (id: number) => api.get<ProductDetail>(`/products/${id}`),
  create: (b: ProductInput) => api.post<ProductDetail>("/products", b),
  update: (id: number, b: Partial<Pick<ProductDetail, "name" | "description" | "brand" | "category_id" | "status">>) =>
    api.put<ProductDetail>(`/products/${id}`, b),
  remove: (id: number) => api.delete<void>(`/products/${id}`),
  reviews: (id: number) => api.get<Review[]>(`/products/${id}/reviews`),
  addReview: (id: number, b: { rating: number; review_text?: string }) =>
    api.post<Review>(`/products/${id}/reviews`, b),
};

export const sellerApi = {
  register: (b: { store_name: string; store_description?: string }) => api.post<Seller>("/sellers/register", b),
  profile: () => api.get<Seller>("/sellers/profile"),
  updateProfile: (b: { store_name?: string; store_description?: string }) => api.put<Seller>("/sellers/profile", b),
  products: () => api.get<ProductDetail[]>("/sellers/products"),
  orders: () => api.get<SellerOrderItem[]>("/sellers/orders"),
  updateListing: (id: number, b: { selling_price?: number; available_quantity?: number }) =>
    api.put<{ id: number; selling_price: number; available_quantity: number }>(`/sellers/listings/${id}`, b),
  updateOrderStatus: (orderId: number, order_status: "shipped" | "delivered") =>
    api.put<Order>(`/sellers/orders/${orderId}/status`, { order_status }),
};

export const uploadApi = {
  image: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ url: string }>("/uploads/images", { method: "POST", body: form });
  },
};

export const cartApi = {
  get: () => api.get<Cart>("/cart"),
  add: (seller_listing_id: number, quantity: number) => api.post<Cart>("/cart/items", { seller_listing_id, quantity }),
  update: (id: number, quantity: number) => api.put<Cart>(`/cart/items/${id}`, { quantity }),
  remove: (id: number) => api.delete<Cart>(`/cart/items/${id}`),
};

export const wishlistApi = {
  list: () => api.get<ProductCard[]>("/wishlist"),
  add: (productId: number) => api.post<void>(`/wishlist/${productId}`),
  remove: (productId: number) => api.delete<void>(`/wishlist/${productId}`),
};

export const orderApi = {
  create: (shipping_address_id: number, idempotency_key?: string) =>
    api.post<Order>("/orders", { shipping_address_id, idempotency_key }),
  list: () => api.get<Order[]>("/orders"),
  get: (id: number) => api.get<Order>(`/orders/${id}`),
  cancel: (id: number) => api.post<Order>(`/orders/${id}/cancel`),
};

export const paymentApi = {
  initiate: (orderId: number) => api.post<PaymentInit>(`/payments/orders/${orderId}/initiate`),
  mockComplete: (paymentId: number, success: boolean) =>
    api.post<Order>(`/payments/mock/${paymentId}/complete`, { success }),
};

export const aiApi = {
  search: (b: {
    query: string;
    filters?: AIFilters;
    conversation_id?: number;
    sort_by?: string;
    page?: number;
    page_size?: number;
  }) => api.post<AISearchResponse>("/ai/search", b),
  compare: (product_ids: number[]) => api.post<AICompareResponse>("/ai/compare", { product_ids }),
};

export const adminApi = {
  dashboard: () => api.get<AdminDashboard>("/admin/dashboard"),
  sellers: (status?: string) => api.get<Seller[]>("/admin/sellers", { status }),
  approve: (id: number) => api.put<Seller>(`/admin/sellers/${id}/approve`),
  reject: (id: number) => api.put<Seller>(`/admin/sellers/${id}/reject`),
  orders: () => api.get<Order[]>("/admin/orders"),
  addCategory: (b: { name: string; description?: string; parent_category_id?: number }) =>
    api.post<Category>("/admin/categories", b),
};
