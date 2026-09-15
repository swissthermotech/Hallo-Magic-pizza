export type Lang = "fr" | "de";
export type I18nText = { fr: string; de: string };

export interface Ingredient {
  id: string;
  fr: string;
  de: string;
}

export interface Category {
  id: string;
  slug: string;
  name: I18nText;
  sort: number;
  image_url?: string | null;
  active: boolean;
  filter?: string | null;
}

export interface SizeOption {
  key: string;
  label: string;
  price: number;
}

export interface ProductOption {
  key: string;
  group: string;
  name: I18nText;
  price: number;
  price_by_size: Record<string, number>;
  only_sizes: string[];
  default: boolean;
}

export interface Extra {
  id: string;
  key: string;
  name: I18nText;
  price: number;
  available: boolean;
  max_quantity: number;
}

export interface WineInfo {
  type?: string | null;
  origin?: string | null;
  bottle_size?: string | null;
}

export interface Product {
  id: string;
  category_id: string;
  name: I18nText;
  description: I18nText;
  price: number;
  sizes: SizeOption[];
  options: ProductOption[];
  image_url?: string | null;
  ingredients: Ingredient[];
  allowed_extra_ids: string[];
  customizable: boolean;
  allergens: I18nText;
  available: boolean;
  is_alcohol: boolean;
  wine?: WineInfo | null;
  sort: number;
}

export interface DeliveryZone {
  npa: string;
  city: string;
  minimum_order: number;
}

export interface Settings {
  restaurant_name: string;
  phone: string;
  address: string;
  opening_hours: Record<string, string>;
  temporarily_closed: boolean;
  closed_message: I18nText;
  delivery_enabled: boolean;
  pickup_enabled: boolean;
  minimum_order: number;
  delivery_fee: number;
  free_delivery_from?: number | null;
  delivery_zones: DeliveryZone[];
}

export interface Menu {
  categories: Category[];
  products: Product[];
  extras: Extra[];
  settings: Settings;
}

export type OrderType = "pickup" | "delivery";
export type OrderStatus =
  | "pending"
  | "accepted"
  | "preparing"
  | "ready"
  | "picked_up"
  | "assigned"
  | "delivering"
  | "delivered"
  | "completed"
  | "cancelled";

export interface OrderExtra {
  extra_id: string;
  name: I18nText;
  unit_price: number;
  quantity: number;
}

export interface OrderItemOption {
  key: string;
  name: I18nText;
  price: number;
}

export interface OrderItem {
  product_id: string;
  name: I18nText;
  unit_price: number;
  quantity: number;
  size?: SizeOption | null;
  options: OrderItemOption[];
  removed_ingredients: Ingredient[];
  extras: OrderExtra[];
  note?: string | null;
  line_total: number;
}

export interface Customer {
  first_name: string;
  last_name: string;
  phone: string;
  email?: string | null;
}

export interface Address {
  street: string;
  number: string;
  npa: string;
  city: string;
  instructions?: string | null;
}

export interface Notification {
  event: string;
  title: I18nText;
  body: I18nText;
  created_at: string;
}

export interface Order {
  id: string;
  order_number: number;
  type: OrderType;
  source: string;
  status: OrderStatus;
  items: OrderItem[];
  customer: Customer;
  address?: Address | null;
  requested_time?: string | null;
  general_note?: string | null;
  payment_method: string;
  language: string;
  subtotal: number;
  extras_total: number;
  delivery_fee: number;
  total: number;
  created_at: string;
  accepted_at?: string | null;
  estimated_minutes?: number | null;
  estimated_ready_at?: string | null;
  time_changed: boolean;
  delay_minutes_total: number;
  reject_reason?: string | null;
  printed: boolean;
  printed_at?: string | null;
  print_attempts: number;
  print_status?: string | null;
  notifications: Notification[];
  status_history: { status: string; at: string }[];
}

// Cart
export interface CartExtra {
  extra_id: string;
  key: string;
  name: I18nText;
  unit_price: number;
  quantity: number;
}

export interface CartItem {
  line_id: string;
  product_id: string;
  name: I18nText;
  image_url?: string | null;
  unit_price: number; // size price + selected options
  quantity: number;
  size?: SizeOption | null;
  options: OrderItemOption[];
  removed_ingredients: Ingredient[];
  extras: CartExtra[];
  note: string;
  is_alcohol: boolean;
}
