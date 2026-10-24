// Mirrors apps/flashcart-api/app/schemas.py. All money values are integer paise.

export type Role = "customer" | "admin";
export type Category = "Electronics" | "Fashion" | "Foods" | "Furniture" | "Tools";
export type Shipping = "regular" | "economic" | "next_day" | "instant";
export type Color = "red" | "blue" | "orange" | "black" | "white" | "green" | "grey";
export type SortKey = "rating" | "price_asc" | "price_desc" | "popular" | "newest";
export type OrderStatus = "confirmed" | "paid" | "shipped" | "delivered" | "cancelled";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export interface Product {
  id: string;
  sku: string;
  slug: string;
  name: string;
  brand: string;
  category: Category;
  description: string;
  price_paise: number;
  currency: "INR";
  images: string[];
  colors: Color[];
  shipping: Shipping[];
  rating: number;
  review_count: number;
  sold_count: number;
  stock: number;
  location: string;
  version: number;
  active: boolean;
}

export interface ProductPage {
  items: Product[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface Facets {
  categories: { value: Category; count: number }[];
  price_min_paise: number;
  price_max_paise: number;
}

export interface CartLine {
  product_id: string;
  name: string;
  image: string | null;
  unit_price_paise: number;
  quantity: number;
  line_total_paise: number;
  in_stock: boolean;
  available: number;
}

export interface Cart {
  items: CartLine[];
  subtotal_paise: number;
  shipping_paise: number;
  total_paise: number;
  item_count: number;
}

export interface Address {
  full_name: string;
  line1: string;
  city: string;
  postal_code: string;
  phone: string;
}

export interface OrderItem {
  product_id: string;
  name: string;
  unit_price_paise: number;
  quantity: number;
  line_total_paise: number;
}

export interface Order {
  id: string;
  order_number: string;
  status: OrderStatus;
  items: OrderItem[];
  subtotal_paise: number;
  shipping_paise: number;
  total_paise: number;
  shipping_method: Shipping;
  shipping_address: Address;
  created_at: string;
  user_email?: string | null;
}

export interface OrderPage {
  items: Order[];
  page: number;
  page_size: number;
  total: number;
}

export interface AdminStats {
  last_30_days: { orders: number; revenue_paise: number };
  orders_by_status: Partial<Record<OrderStatus, number>>;
  products_active: number;
  low_stock: number;
  customers: number;
}

export interface ShortageDetail {
  message: string;
  items?: { product_id: string; name: string; requested: number; available: number }[];
  total_paise?: number;
}
