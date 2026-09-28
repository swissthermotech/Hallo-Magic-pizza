import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { storage } from "@/src/utils/storage";
import { api, setStaffToken, setStaffUnauthorizedHandler } from "@/src/api";

const KEY = "staff_session";
export type StaffRole = "manager" | "kitchen" | "phone" | "driver1" | "driver2" | "driver3";

interface StaffCtx {
  ready: boolean;
  unlocked: boolean;
  role: StaffRole | null;
  label: string;
  isDriver: boolean;
  driverName: string | null; // "Livreur 1" ...
  unlock: (password: string) => Promise<StaffRole | null>;
  lastError: string | null; // server message of the last failed unlock (wrong password / attempts left / 15-min lockout / inactive position)
  adoptToken: (token: string) => Promise<void>; // fresh token after the manager changed its own password
  lock: () => void;
}

const Ctx = createContext<StaffCtx>({ ready: false, unlocked: false, role: null, label: "", isDriver: false, driverName: null, unlock: async () => null, adoptToken: async () => {}, lock: () => {}, lastError: null });

/** Server-side staff authentication: the password (or driver shift code) is verified by the backend (Argon2 hashes),
 * which returns a role JWT that expires with the working day. Brute force is throttled server-side. Nothing secret lives in the frontend. */
export function StaffProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<{ token: string; role: StaffRole; label: string } | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  useEffect(() => {
    storage.secureGet<string>(KEY, "").then(async (raw) => {
      if (raw) {
        try {
          const s = JSON.parse(raw);
          setStaffToken(s.token);
          const me = await api.get<{ role: StaffRole; label: string }>("/auth/staff/me");
          setSession({ token: s.token, role: me.role, label: me.label });
        } catch {
          setStaffToken(null);
          await storage.secureRemove(KEY);
        }
      }
      setReady(true);
    });
  }, []);

  const unlock = useCallback(async (password: string) => {
    try {
      const r = await api.post<{ access_token: string; role: StaffRole; label: string }>("/auth/staff/login", { password: password.trim() });
      setStaffToken(r.access_token);
      const s = { token: r.access_token, role: r.role, label: r.label };
      setSession(s);
      await storage.secureSet(KEY, JSON.stringify(s));
      setLastError(null);
      return r.role;
    } catch (e: any) {
      // 401 (wrong password, attempts left), 429 (blocked 15 min), 403 (inactive position): show the server's reason
      setLastError(e?.message || null);
      return null;
    }
  }, []);
  const adoptToken = useCallback(async (token: string) => {
    setStaffToken(token);
    setSession((s) => {
      const next = s ? { ...s, token } : s;
      if (next) storage.secureSet(KEY, JSON.stringify(next));
      return next;
    });
  }, []);
  const lock = useCallback(() => {
    setSession(null);
    setStaffToken(null);
    storage.secureRemove(KEY);
  }, []);

  // Expired / revoked staff token (401 on any staff request, e.g. an iPad left open overnight): lock immediately so the
  // person sees the PIN screen with the reason instead of silently failing saves while the (public) menu still displays.
  useEffect(() => {
    setStaffUnauthorizedHandler((message) => {
      setLastError(message || "Session expirée – veuillez saisir votre code");
      lock();
    });
    return () => setStaffUnauthorizedHandler(null);
  }, [lock]);

  const value = useMemo<StaffCtx>(() => {
    const role = session?.role ?? null;
    const isDriver = !!role && role.startsWith("driver");
    return { ready, unlocked: !!session, role, label: session?.label ?? "", isDriver, driverName: isDriver ? `Livreur ${role!.slice(-1)}` : null, unlock, adoptToken, lock, lastError };
  }, [ready, session, unlock, adoptToken, lock, lastError]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useStaff = () => useContext(Ctx);

/** Where a role lands after login. */
export function homeFor(role: StaffRole): "/staff" | "/phone-orders" | "/driver" {
  if (role.startsWith("driver")) return "/driver";
  if (role === "phone") return "/phone-orders";
  return "/staff";
}
