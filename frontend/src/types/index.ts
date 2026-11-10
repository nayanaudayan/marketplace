export type Role = "customer" | "seller" | "admin";

export interface User {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  role: Role;
  status: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  user: User;
}

export interface Address {
  id: number;
  address_line: string;
  city: string;
  state: string;
  country: string;
  postal_code: string;
  is_default: boolean;
}

export interface Category {
  id: number;
  name: string;
  description: string | null;
  parent_category_id: number | null;
}

export interface ProductCard {
  id: number;
  name: string;
  brand: string | null;
  description: string;
  category_id: number;
  category_name: string;
  primary_image_url: string | null;
  min_price: number | null;
  in_stock: boolean;
  avg_rating: number | null;
  review_count: number;
}

export interface Listing {
  id: number;
  seller_id: number;
  seller_name: string;
  selling_price: number;
  available_quantity: number;
}

export interface Variant {
  id: number;
  sku: string;
  variant_name: string;
  attributes: Record<string, unknown>;
  listings: Listing[];
}

export interface ProductDetail extends ProductCard {
  specifications: Record<string, unknown>;
  status: string;
  seller_id: number;
  images: { id: number; image_url: string; is_primary: boolean }[];
  variants: Variant[];
}

export interface ProductList {
  total: number;
  page: number;
  page_size: number;
  items: ProductCard[];
}

export interface ProductInput {
  category_id: number;
  name: string;
  description: string;
  brand?: string;
  specifications?: Record<string, unknown>;
  image_urls?: string[];
  variants: {
    sku: string;
    variant_name: string;
    attributes?: Record<string, unknown>;
    selling_price: number;
    quantity: number;
  }[];
}

export interface Review {
  id: number;
  user_id: number;
  user_name: string;
  product_id: number;
  rating: number;
  review_text: string | null;
  created_at: string;
}

export interface Seller {
  id: number;
  user_id: number;
  store_name: string;
  store_description: string | null;
  approval_status: "pending" | "approved" | "rejected";
  commission_percentage: number;
  user_email?: string;
  user_name?: string;
}

export type OrderStatus = "pending" | "confirmed" | "shipped" | "delivered" | "cancelled";
export type PaymentStatus = "pending" | "paid" | "failed" | "refunded";

export interface SellerOrderItem {
  order_id: number;
  order_number: string;
  order_status: OrderStatus;
  product_name: string;
  quantity: number;
  subtotal: number;
  created_at: string;
}

export interface CartItem {
  id: number;
  seller_listing_id: number;
  product_id: number;
  product_name: string;
  variant_name: string;
  seller_name: string;
  image_url: string | null;
  unit_price: number;
  quantity: number;
  available_quantity: number;
  subtotal: number;
}

export interface Cart {
  items: CartItem[];
  total: number;
}

export interface OrderItem {
  id: number;
  seller_listing_id: number;
  product_name_snapshot: string;
  price_snapshot: number;
  quantity: number;
  subtotal: number;
}

export interface Order {
  id: number;
  order_number: string;
  total_amount: number;
  payment_status: PaymentStatus;
  order_status: OrderStatus;
  shipping_address_id: number;
  created_at: string;
  items: OrderItem[];
}

export interface PaymentInit {
  payment_id: number;
  provider: string;
  status: string;
  amount: number;
}

export interface AIFilters {
  category?: string;
  max_price?: number;
  min_price?: number;
  minimum_ram_gb?: number;
  brand?: string;
}

export interface AIProduct extends ProductCard {
  listing_id: number;
  price: number;
  stock: number;
  seller_name: string;
  score: number;
  match_reason: string;
}

export interface AISearchResponse {
  query: string;
  conversation_id: number;
  extracted_filters: Record<string, unknown>;
  total: number;
  explanation: string;
  products: AIProduct[];
}

export interface AICompareResponse {
  products: ProductDetail[];
  summary: string;
}

export interface AdminDashboard {
  users: number;
  sellers: number;
  pending_sellers: number;
  products: number;
  orders: number;
  revenue: number;
}
