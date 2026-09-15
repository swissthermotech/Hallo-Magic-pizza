import { Platform } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Menu, Order, Product, Extra, Settings, OrderType, CartItem, Customer, Address } from "./types";

const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

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
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
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
  });
}

export function useTicket(id: string | undefined) {
  return useQuery({
    queryKey: ["ticket", id],
    queryFn: () => api.get<{ text: string; printed: boolean; printed_at?: string; print_attempts: number; order_number: number }>(`/orders/${id}/ticket`),
    enabled: !!id,
  });
}

// ---- Mutations ----
export interface PlaceOrderPayload {
  type: OrderType;
  items: CartItem[];
  customer: Customer;
  address?: Address;
  requested_time?: string;
  general_note?: string;
  age_confirmed: boolean;
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
        general_note: p.general_note,
        age_confirmed: p.age_confirmed,
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
