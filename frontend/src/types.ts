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
  price_by_size?: Record<string, number> | null; // 32 / 40 / 50 cm supplement prices
  available: boolean;
  max_quantity: number;
  vat_rate?: number | null;
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
  origin?: I18nText;
  available: boolean;
  is_alcohol: boolean;
  alcohol_type?: AlcoholType | null;
  images: string[];
  wine?: WineInfo | null;
  sort: number;
  vat_rate?: number | null;
  highlight?: "moment" | "custom" | null; // Pizza du moment / Créez votre pizza – listed first
  available_from?: string | null;
  available_until?: string | null;
}

export type AlcoholType = "fermented" | "spirits";
/** 16+ for fermented drinks (beer, wine, prosecco), 18+ for spirits; a mixed selection requires 18+. */
export function requiredAge(items: { is_alcohol: boolean; alcohol_type?: AlcoholType | null }[]): 16 | 18 | null {
  const ages = items.filter((i) => i.is_alcohol).map((i) => (i.alcohol_type === "spirits" ? 18 : 16));
  return ages.length ? (Math.max(...ages) as 16 | 18) : null;
}

export interface SavedAddress {
  id: string;
  label: string;
  street: string;
  number: string;
  npa: string;
  city: string;
  instructions?: string | null;
}

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  email?: string | null;
  addresses: SavedAddress[];
  created_at: string;
}

export interface DeliveryZone {
  npa: string;
  city: string;
  minimum_order: number;
}

export interface Settings {
  restaurant_name: string;
  business_name: string;
  street: string;
  postal_code: string;
  city: string;
  vat_number: string;
  vat_rate_standard: number;
  vat_rate_alcohol: number;
  delivery_fee_vat_rate: number;
  phone: string;
  address: string;
  opening_hours: Record<string, string>;
  first_delivery?: Record<string, string>;
  meat_fish_origin?: I18nText;
  temporarily_closed: boolean;
  closed_message: I18nText;
  delivery_enabled: boolean;
  pickup_enabled: boolean;
  minimum_order: number;
  delivery_fee: number;
  free_delivery_from?: number | null;
  delivery_zones: DeliveryZone[];
  hero_images?: string[];
  public_url?: string;
  review_enabled?: boolean;
  google_review_url?: string;
  legal_privacy?: I18nText;
  legal_terms?: I18nText;
  legal_imprint?: I18nText;
  review_delay_minutes?: number;
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
  half?: { product_id: string; name: I18nText; removed_ingredients: Ingredient[]; note?: string | null } | null; // MOITIÉ/MOITIÉ (phone orders)
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

export interface VatGroup {
  rate: number;
  gross: number;
  net: number;
  vat: number;
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
  requested_date?: string | null; // future-day (scheduled) order
  legacy?: boolean; // created before the printer went live (test data) – shown in Historique only
  scheduled_for?: string | null;
  general_note?: string | null;
  payment_method: string;
  language: string;
  age_confirmed: boolean;
  age_required?: 16 | 18 | null;
  user_id?: string | null;
  station?: number | null;
  driver?: string | null;
  driver_name?: string | null;
  assigned_at?: string | null;
  picked_up_at?: string | null;
  out_for_delivery_at?: string | null;
  delivered_at?: string | null;
  ready_at?: string | null;
  collection_method?: string | null;
  amount_due: number;
  payment_collected: boolean;
  collected_at?: string | null;
  printnode_job_id?: string | null;
  last_print_error?: string | null;
  subtotal: number;
  extras_total: number;
  delivery_fee: number;
  total: number;
  subtotal_gross: number;
  delivery_fee_gross: number;
  delivery_fee_vat_rate: number;
  discount_gross: number;
  total_gross: number;
  vat_breakdown: VatGroup[];
  total_vat: number;
  total_net: number;
  paid: boolean;
  receipt_printed: boolean;
  receipt_printed_at?: string | null;
  receipt_print_attempts: number;
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
  alcohol_type?: AlcoholType | null;
  half?: { product_id: string; name: I18nText; removed_ingredients: Ingredient[]; note: string } | null; // MOITIÉ/MOITIÉ (phone orders)
}
