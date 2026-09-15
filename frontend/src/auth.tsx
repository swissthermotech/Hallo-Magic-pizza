import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { storage } from "@/src/utils/storage";
import { authApi, setAuthToken } from "@/src/api";
import type { SavedAddress, User } from "@/src/types";

const TOKEN_KEY = "customer_token";

interface AuthCtx {
  ready: boolean;
  user: User | null;
  login: (phone: string, password: string) => Promise<void>;
  register: (body: { first_name: string; last_name: string; phone: string; email?: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  updateProfile: (body: { first_name: string; last_name: string; phone: string; email?: string }) => Promise<void>;
  addAddress: (a: Omit<SavedAddress, "id">) => Promise<void>;
  updateAddress: (id: string, a: Omit<SavedAddress, "id">) => Promise<void>;
  deleteAddress: (id: string) => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

/** Optional customer account. Everything works without logging in (guest checkout). */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const qc = useQueryClient();

  useEffect(() => {
    storage.secureGet<string>(TOKEN_KEY, "").then(async (tok) => {
      if (tok) {
        setAuthToken(tok);
        try {
          setUser(await authApi.me());
        } catch {
          setAuthToken(null);
          await storage.secureRemove(TOKEN_KEY);
        }
      }
      setReady(true);
    });
  }, []);

  const session = useCallback(async (r: { access_token: string; user: User }) => {
    setAuthToken(r.access_token);
    await storage.secureSet(TOKEN_KEY, r.access_token);
    setUser(r.user);
    qc.invalidateQueries({ queryKey: ["orders"] });
  }, [qc]);

  const login = useCallback(async (phone: string, password: string) => session(await authApi.login({ phone, password })), [session]);
  const register = useCallback(async (body: Parameters<AuthCtx["register"]>[0]) => session(await authApi.register(body)), [session]);
  const logout = useCallback(async () => {
    setAuthToken(null);
    await storage.secureRemove(TOKEN_KEY);
    setUser(null);
    qc.removeQueries({ queryKey: ["orders", "account"] });
  }, [qc]);
  const refresh = useCallback(async () => {
    if (user) setUser(await authApi.me());
  }, [user]);
  const updateProfile = useCallback(async (body: Parameters<AuthCtx["updateProfile"]>[0]) => setUser(await authApi.updateProfile(body)), []);
  const addAddress = useCallback(async (a: Omit<SavedAddress, "id">) => setUser(await authApi.addAddress(a)), []);
  const updateAddress = useCallback(async (id: string, a: Omit<SavedAddress, "id">) => setUser(await authApi.updateAddress(id, a)), []);
  const deleteAddress = useCallback(async (id: string) => setUser(await authApi.deleteAddress(id)), []);

  const value = useMemo<AuthCtx>(
    () => ({ ready, user, login, register, logout, refresh, updateProfile, addAddress, updateAddress, deleteAddress }),
    [ready, user, login, register, logout, refresh, updateProfile, addAddress, updateAddress, deleteAddress],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("AuthProvider missing");
  return c;
}
