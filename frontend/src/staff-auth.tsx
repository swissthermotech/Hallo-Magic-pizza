import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { storage } from "@/src/utils/storage";
import { api, setStaffToken } from "@/src/api";

const KEY = "staff_session";
export type StaffRole = "manager" | "kitchen" | "phone" | "driver1" | "driver2" | "driver3";

interface StaffCtx {
  ready: boolean;
  unlocked: boolean;
  role: StaffRole | null;
  label: string;
  isDriver: boolean;
  driverName: string | null; // "Livreur 1" ...
  unlock: (pin: string) => Promise<StaffRole | null>;
  lock: () => void;
}

const Ctx = createContext<StaffCtx>({ ready: false, unlocked: false, role: null, label: "", isDriver: false, driverName: null, unlock: async () => null, lock: () => {} });

/** Server-side staff authentication: the PIN is verified by the backend (Argon2 hashes), which returns a role JWT.
 * Nothing secret lives in the frontend. Roles: manager, kitchen, phone, driver1..3. */
export function StaffProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<{ token: string; role: StaffRole; label: string } | null>(null);

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

  const unlock = useCallback(async (pin: string) => {
    try {
      const r = await api.post<{ access_token: string; role: StaffRole; label: string }>("/auth/staff/login", { pin: pin.trim() });
      setStaffToken(r.access_token);
      const s = { token: r.access_token, role: r.role, label: r.label };
      setSession(s);
      await storage.secureSet(KEY, JSON.stringify(s));
      return r.role;
    } catch {
      return null;
    }
  }, []);
  const lock = useCallback(() => {
    setSession(null);
    setStaffToken(null);
    storage.secureRemove(KEY);
  }, []);

  const value = useMemo<StaffCtx>(() => {
    const role = session?.role ?? null;
    const isDriver = !!role && role.startsWith("driver");
    return { ready, unlocked: !!session, role, label: session?.label ?? "", isDriver, driverName: isDriver ? `Livreur ${role!.slice(-1)}` : null, unlock, lock };
  }, [ready, session, unlock, lock]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useStaff = () => useContext(Ctx);

/** Where a role lands after login. */
export function homeFor(role: StaffRole): "/staff" | "/phone-orders" | "/driver" {
  if (role.startsWith("driver")) return "/driver";
  if (role === "phone") return "/phone-orders";
  return "/staff";
}
