import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { storage } from "@/src/utils/storage";
import type { CartItem, OrderType } from "./types";

interface CartCtx {
  items: CartItem[];
  generalNote: string;
  setGeneralNote: (n: string) => void;
  addItem: (item: Omit<CartItem, "line_id">) => void;
  updateItem: (lineId: string, patch: Partial<CartItem>) => void;
  removeItem: (lineId: string) => void;
  clear: () => void;
  count: number;
  subtotal: number;
  extrasTotal: number;
  hasAlcohol: boolean;
  myOrderIds: string[];
  addMyOrder: (id: string) => void;
  orderType: OrderType;
  setOrderType: (t: OrderType) => void;
}

const Ctx = createContext<CartCtx | null>(null);

export const lineTotal = (i: CartItem) =>
  (i.unit_price + i.extras.reduce((s, e) => s + e.unit_price * e.quantity, 0)) * i.quantity;

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);
  const [generalNote, setGeneralNote] = useState("");
  const [myOrderIds, setMyOrderIds] = useState<string[]>([]);
  const [orderType, setOrderType] = useState<OrderType>("pickup");
  const loaded = useRef(false);

  useEffect(() => {
    Promise.all([storage.getItem("cart", "[]"), storage.getItem("my_orders", "[]")]).then(([c, o]) => {
      try {
        setItems(JSON.parse(c as string));
      } catch {}
      try {
        setMyOrderIds(JSON.parse(o as string));
      } catch {}
      loaded.current = true;
    });
  }, []);

  useEffect(() => {
    if (loaded.current) storage.setItem("cart", JSON.stringify(items));
  }, [items]);
  useEffect(() => {
    if (loaded.current) storage.setItem("my_orders", JSON.stringify(myOrderIds));
  }, [myOrderIds]);

  const addItem = useCallback((item: Omit<CartItem, "line_id">) => {
    setItems((prev) => [...prev, { ...item, line_id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}` }]);
  }, []);
  const updateItem = useCallback((lineId: string, patch: Partial<CartItem>) => {
    setItems((prev) => prev.map((i) => (i.line_id === lineId ? { ...i, ...patch } : i)));
  }, []);
  const removeItem = useCallback((lineId: string) => setItems((prev) => prev.filter((i) => i.line_id !== lineId)), []);
  const clear = useCallback(() => {
    setItems([]);
    setGeneralNote("");
  }, []);
  const addMyOrder = useCallback((id: string) => setMyOrderIds((prev) => [id, ...prev.filter((x) => x !== id)].slice(0, 30)), []);

  const value = useMemo<CartCtx>(() => {
    const subtotal = items.reduce((s, i) => s + i.unit_price * i.quantity, 0);
    const extrasTotal = items.reduce((s, i) => s + i.extras.reduce((a, e) => a + e.unit_price * e.quantity, 0) * i.quantity, 0);
    return {
      items,
      generalNote,
      setGeneralNote,
      addItem,
      updateItem,
      removeItem,
      clear,
      count: items.reduce((s, i) => s + i.quantity, 0),
      subtotal,
      extrasTotal,
      hasAlcohol: items.some((i) => i.is_alcohol),
      myOrderIds,
      addMyOrder,
      orderType,
      setOrderType,
    };
  }, [items, generalNote, addItem, updateItem, removeItem, clear, myOrderIds, addMyOrder, orderType]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCart() {
  const c = useContext(Ctx);
  if (!c) throw new Error("CartProvider missing");
  return c;
}
