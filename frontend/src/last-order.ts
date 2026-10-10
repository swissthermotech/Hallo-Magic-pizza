import AsyncStorage from "@react-native-async-storage/async-storage";

/** Last successfully placed order – lets the customer reopen the confirmation/status after a refresh, an app
 *  restart or a lost screen instead of ordering a second time. Kept for 3 hours. */
const KEY = "last_order_v1";
const TTL_MS = 3 * 60 * 60 * 1000;

export interface LastOrder { id: string; number: number; at: number }

export async function saveLastOrder(id: string, number: number): Promise<void> {
  try { await AsyncStorage.setItem(KEY, JSON.stringify({ id, number, at: Date.now() } satisfies LastOrder)); } catch {}
}

export async function loadLastOrder(): Promise<LastOrder | null> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as LastOrder;
    return v && Date.now() - v.at < TTL_MS ? v : null;
  } catch { return null; }
}

/** One idempotency key per checkout attempt (no crypto dependency needed – ~100 bits of randomness + time). */
export function newClientOrderId(): string {
  const rnd = () => Math.random().toString(36).slice(2, 12);
  return `co-${Date.now().toString(36)}-${rnd()}-${rnd()}`;
}
