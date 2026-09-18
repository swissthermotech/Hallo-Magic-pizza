import { Platform } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Menu, Order, Product, Extra, Settings, Category, OrderType, CartItem, Customer, Address, User, SavedAddress } from "./types";

const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

/** Product photos are stored as API-relative urls ("/api/files/..."); external urls (placeholders) pass through. */
export function imgUri(url?: string | null): string | undefined {
  if (!url) return undefined;
  return url.startsWith("/") ? `${process.env.EXPO_PUBLIC_BACKEND_URL}${url}` : url;
}

// Optional customer session – set by AuthProvider; guests simply have no token.
let authToken: string | null = null;
export const setAuthToken = (t: string | null) => {
  authToken = t;
};
let staffToken: string | null = null;
export const setStaffToken = (t: string | null) => {
  staffToken = t;
};
const CUSTOMER_PATHS = ["/auth/register", "/auth/login", "/auth/me", "/me/orders"];
/** Staff devices send the staff role token; customer-account endpoints and customer checkout use the customer token. */
const authHeaders = (path = ""): Record<string, string> => {
  const customer = CUSTOMER_PATHS.some((p) => path.startsWith(p)) || path === "/orders";
  const tok = customer ? authToken : staffToken || authToken;
  return tok ? { Authorization: `Bearer ${tok}` } : {};
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(path), ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) => request<T>(p, { method: "POST", body: JSON.stringify(body ?? {}) }),
  put: <T>(p: string, body: unknown) => request<T>(p, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(p: string, body: unknown) => request<T>(p, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T>(p: string) => request<T>(p, { method: "DELETE" }),
};

export const SOURCE = Platform.select({ ios: "ios", android: "android", default: "web" }) as string;

// ---- Queries ----
export function useMenu(pollMs = 8000) {
  return useQuery({ queryKey: ["menu"], queryFn: () => api.get<Menu>("/menu"), refetchInterval: pollMs });
}

export function useOrder(id: string | undefined, pollMs = 4000) {
  return useQuery({
    queryKey: ["order", id],
    queryFn: () => api.get<Order>(`/orders/${id}`),
    enabled: !!id,
    refetchInterval: pollMs,
    refetchIntervalInBackground: true,
  });
}

export function useOrdersByIds(ids: string[]) {
  return useQuery({
    queryKey: ["orders", "mine", ids.join(",")],
    queryFn: () => api.get<Order[]>(`/orders?ids=${ids.join(",")}`),
    enabled: ids.length > 0,
    refetchInterval: 5000,
  });
}

export function useActiveOrders(pollMs = 3000) {
  return useQuery({
    queryKey: ["orders", "active"],
    queryFn: () => api.get<Order[]>("/orders?active=true"),
    refetchInterval: pollMs,
    refetchIntervalInBackground: true, // manager dashboard keeps syncing driver/payment changes without manual refresh
    refetchOnWindowFocus: true,
  });
}

export function useTicket(id: string | undefined) {
  return useQuery({
    queryKey: ["ticket", id],
    queryFn: () => api.get<{ text: string; printed: boolean; printed_at?: string; print_attempts: number; order_number: number; print_status?: string | null; last_print_error?: string | null; printnode_job_id?: string | null; qr?: string | null; printer_configured: boolean }>(`/orders/${id}/ticket`),
    enabled: !!id,
  });
}

export function useReceipt(id: string | undefined) {
  return useQuery({
    queryKey: ["receipt", id],
    queryFn: () => api.get<{ text: string; printed: boolean; printed_at?: string; print_attempts: number; order_number: number }>(`/orders/${id}/receipt`),
    enabled: !!id,
  });
}

export function usePrintReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, force }: { id: string; force?: boolean }) =>
      api.post<{ printed: boolean; print_attempts: number; text: string }>(`/orders/${id}/receipt/print`, { force: !!force }),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: ["receipt", v.id] });
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}

// ---- Mutations ----
export interface PlaceOrderPayload {
  type: OrderType;
  items: CartItem[];
  customer: Customer;
  address?: Address;
  requested_time?: string;
  requested_date?: string | null; // YYYY-MM-DD for a future day (scheduled order)
  general_note?: string;
  age_confirmed: boolean;
  save_address?: boolean;
  language: string;
}

export function usePlaceOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: PlaceOrderPayload) =>
      api.post<Order>("/orders", {
        type: p.type,
        source: SOURCE,
        items: p.items.map((i) => ({
          product_id: i.product_id,
          quantity: i.quantity,
          size_key: i.size?.key ?? null,
          option_keys: i.options.map((o) => o.key),
          removed_ingredient_ids: i.removed_ingredients.map((r) => r.id),
          extras: i.extras.map((e) => ({ extra_id: e.extra_id, quantity: e.quantity })),
          note: i.note || null,
        })),
        customer: p.customer,
        address: p.address,
        requested_time: p.requested_time,
        requested_date: p.requested_date ?? null,
        general_note: p.general_note,
        age_confirmed: p.age_confirmed,
        save_address: !!p.save_address,
        language: p.language,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });
}

export function useOrderAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, body }: { id: string; action: "accept" | "reject" | "delay" | "status"; body: object }) =>
      api.post<Order>(`/orders/${id}/${action}`, body),
    onSuccess: (o) => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["order", o.id] });
      qc.invalidateQueries({ queryKey: ["ticket", o.id] });
    },
  });
}

export function usePrintTicket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, force }: { id: string; force?: boolean }) =>
      api.post<{ printed: boolean; print_attempts: number; text: string }>(`/orders/${id}/print`, { force: !!force }),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: ["ticket", v.id] });
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}

export function useSaveProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Partial<Product> }) =>
      id ? api.patch<Product>(`/products/${id}`, body) : api.post<Product>("/products", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["menu"] }),
  });
}

export function useDeleteProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/products/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["menu"] }),
  });
}

export function useSaveCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Omit<Category, "id"> }) =>
      id ? api.put<Category>(`/categories/${id}`, body) : api.post<Category>("/categories", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["menu"] }),
  });
}
export const exportMenu = () => api.get<object>("/admin/export");

export function useSaveExtra() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Omit<Extra, "id"> }) =>
      id ? api.put<Extra>(`/extras/${id}`, body) : api.post<Extra>("/extras", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["menu"] }),
  });
}

export function useSaveSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Settings) => api.put<Settings>("/settings", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["menu"] }),
  });
}

// ---- Customer accounts (optional) ----
export interface AuthResponse {
  access_token: string;
  user: User;
}
export const authApi = {
  register: (body: { first_name: string; last_name: string; phone: string; email?: string; password: string }) => api.post<AuthResponse>("/auth/register", body),
  login: (body: { phone: string; password: string }) => api.post<AuthResponse>("/auth/login", body),
  me: () => api.get<User>("/auth/me"),
  updateProfile: (body: { first_name: string; last_name: string; phone: string; email?: string }) => api.put<User>("/auth/me", body),
  addAddress: (body: Omit<SavedAddress, "id">) => api.post<User>("/auth/me/addresses", body),
  updateAddress: (id: string, body: Omit<SavedAddress, "id">) => api.put<User>(`/auth/me/addresses/${id}`, body),
  deleteAddress: (id: string) => api.del<User>(`/auth/me/addresses/${id}`),
};

export function useMyAccountOrders(enabled: boolean) {
  return useQuery({ queryKey: ["orders", "account"], queryFn: () => api.get<Order[]>("/me/orders"), enabled, refetchInterval: 8000 });
}

export function useCustomerSearch(phone: string) {
  const q = phone.replace(/\D/g, "");
  return useQuery({
    queryKey: ["customers", q],
    queryFn: () => api.get<{ accounts: User[]; orders: Order[] }>(`/customers/search?phone=${encodeURIComponent(q)}`),
    enabled: q.length >= 3,
  });
}

// ---- Phone orders (staff iPads) ----
export interface PhoneOrderPayload extends PlaceOrderPayload {
  station: number;
  payment_method: string;
  customer_id?: string | null;
  client_request_id?: string;
}
export function usePlacePhoneOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: PhoneOrderPayload) =>
      api.post<Order>("/phone-orders", {
        type: p.type,
        source: "telephone",
        station: p.station,
        payment_method: p.payment_method,
        customer_id: p.customer_id ?? null,
        client_request_id: p.client_request_id,
        items: p.items.map((i) => ({
          product_id: i.product_id,
          quantity: i.quantity,
          size_key: i.size?.key ?? null,
          option_keys: i.options.map((o) => o.key),
          removed_ingredient_ids: i.removed_ingredients.map((r) => r.id),
          extras: i.extras.map((e) => ({ extra_id: e.extra_id, quantity: e.quantity })),
          note: i.note || null,
          half_product_id: i.half?.product_id ?? null,
          half_removed_ingredient_ids: i.half?.removed_ingredients.map((r) => r.id) ?? [],
          half_note: i.half?.note || null,
        })),
        customer: p.customer,
        address: p.address,
        requested_time: p.requested_time,
        requested_date: p.requested_date ?? null,
        general_note: p.general_note,
        age_confirmed: true,
        save_address: !!p.save_address,
        language: p.language,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });
}
export const customersApi = {
  create: (body: { first_name: string; last_name: string; phone: string; email?: string; address?: Omit<SavedAddress, "id"> | null }) => api.post<User>("/customers", body),
  addAddress: (id: string, body: Omit<SavedAddress, "id">) => api.post<User>(`/customers/${id}/addresses`, body),
};
export function useAssignDriver() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, driver }: { id: string; driver: string }) => api.post<Order>(`/orders/${id}/assign`, { driver }),
    onSuccess: (o) => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["order", o.id] });
    },
  });
}

// ---- Product photo upload (admin) ----
export async function uploadProductPhoto(uri: string, name = "photo.jpg", type = "image/jpeg"): Promise<{ url: string; path: string; size: number }> {
  const form = new FormData();
  if (Platform.OS === "web") {
    const blob = await (await fetch(uri)).blob();
    form.append("file", blob, name);
  } else {
    form.append("file", { uri, name, type } as any);
  }
  const res = await fetch(`${BASE}/uploads/product-photo`, { method: "POST", body: form, headers: authHeaders() });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

// ---- Driver ----
export function useDriverOrders() {
  return useQuery({ queryKey: ["orders", "driver"], queryFn: () => api.get<Order[]>("/driver/orders"), refetchInterval: 5000 });
}
export function useDriverAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, body }: { id: string; action: "pickup" | "depart" | "delivered" | "collect"; body?: object }) => api.post<Order>(`/driver/orders/${id}/${action}`, body ?? {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });
}

// ---- Manager reports ----
export interface DriverClosing {
  driver: string; driver_name?: string | null; label: string; identity_key: string; legacy: boolean; is_current: boolean; date: string; deliveries: number; cancelled: number;
  orders: { id: string; order_number: number; total: number; collection_method: string; payment_collected: boolean; delivered_at?: string | null; status: string; city: string }[];
  cash_expected: number; terminal_expected: number; paid_no_collection: number; total: number;
  actual_cash?: number | null; actual_terminal?: number | null; cash_difference?: number | null; terminal_difference?: number | null; closed_at?: string | null;
}
export function useClosing(date: string) {
  return useQuery({ queryKey: ["closing", date], queryFn: () => api.get<{ date: string; drivers: DriverClosing[] }>(`/reports/closing?date=${date}`), refetchInterval: 10000 });
}
export function useSources(date: string) {
  return useQuery({ queryKey: ["sources", date], queryFn: () => api.get<{ date: string; sources: { source: string; count: number; total: number }[]; total_count: number; total: number }>(`/reports/sources?date=${date}`), refetchInterval: 10000 });
}
export function useSaveClosing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { date: string; driver: string; driver_name?: string | null; actual_cash?: number | null; actual_terminal?: number | null }) => api.post("/reports/closing", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["closing"] }),
  });
}
export const staffPins = {
  roles: () => api.get<{ role: string; label: string; active: boolean }[]>("/auth/staff/roles"),
  change: (role: string, pin: string) => api.put("/auth/staff/pins", { role, pin }),
  setActive: (role: string, active: boolean) => api.put<{ role: string; active: boolean }>(`/auth/staff/drivers/${role}/active`, { active }),
};

// ---- Ordering hours / first delivery ----
export interface OrderingDay { date: string; weekday: string; is_today: boolean; is_tomorrow: boolean; pickup_slots: string[]; delivery_slots: string[] }
export interface OrderingStatus { open_now: boolean; pickup_open: boolean; delivery_open: boolean; delivery_from?: string | null; next_open?: string | null; pickup_slots: string[]; delivery_slots: string[]; days: OrderingDay[] }
export function useOrderingStatus() {
  return useQuery({ queryKey: ["ordering"], queryFn: () => api.get<OrderingStatus>("/settings/ordering"), refetchInterval: 60000 });
}
export function useSetFirstDelivery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { lunch?: string; evening?: string }) => api.put<{ first_delivery: Record<string, string> }>("/settings/first-delivery", body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["menu"] }); qc.invalidateQueries({ queryKey: ["ordering"] }); },
  });
}
// ---- Driver shifts (manager) ----
export interface Shift { role: string; driver: string; name: string | null; opened_at?: string | null; expires_at?: string | null; connected: boolean; pin?: string }
export const shiftsApi = {
  list: () => api.get<Shift[]>("/auth/staff/shifts"),
  open: (role: string, name: string) => api.post<Shift>(`/auth/staff/shifts/${role}/open`, { name }),
  reset: (role: string) => api.post(`/auth/staff/shifts/${role}/reset-session`, {}),
  close: (role: string) => api.post(`/auth/staff/shifts/${role}/close`, {}),
};
/** Current person on each driver slot (manager / kitchen / phone) – for the assignment buttons. */
export interface DriverSlot { role: string; driver: string; name: string | null; open: boolean; label: string }
export function useDriverSlots() {
  return useQuery({ queryKey: ["driver-slots"], queryFn: () => api.get<DriverSlot[]>("/auth/staff/drivers"), refetchInterval: 15000 });
}
