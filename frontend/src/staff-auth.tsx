import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { storage } from "@/src/utils/storage";

const KEY = "staff_unlocked";

interface StaffCtx {
  ready: boolean;
  unlocked: boolean;
  unlock: (pin: string) => boolean;
  lock: () => void;
}

const Ctx = createContext<StaffCtx>({ ready: false, unlocked: false, unlock: () => false, lock: () => {} });

/** Client-side PIN gate for the staff area (dashboard / kitchen / admin). */
export function StaffProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [unlocked, setUnlocked] = useState(false);

  useEffect(() => {
    storage.getItem<boolean>(KEY, false).then((v) => {
      setUnlocked(!!v);
      setReady(true);
    });
  }, []);

  const unlock = useCallback((pin: string) => {
    const ok = pin.trim() === String(process.env.EXPO_PUBLIC_STAFF_PIN ?? "");
    if (ok) {
      setUnlocked(true);
      storage.setItem(KEY, true);
    }
    return ok;
  }, []);
  const lock = useCallback(() => {
    setUnlocked(false);
    storage.removeItem(KEY);
  }, []);

  const value = useMemo(() => ({ ready, unlocked, unlock, lock }), [ready, unlocked, unlock, lock]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useStaff = () => useContext(Ctx);
