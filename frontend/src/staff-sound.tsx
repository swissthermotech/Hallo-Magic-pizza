import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Platform } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useAudioPlayer } from "expo-audio";
import { useActiveOrders } from "@/src/api";
import { isScheduledLater } from "@/src/components/staff-order";
import type { Order } from "@/src/types";

const ALERT = require("../assets/sounds/new-order.wav");
const STORAGE_KEY = "staff_sound_on";
const REPEAT_MS = 20000;

// Browser autoplay policy: audio must be started once by a user gesture per page session. Kept at module level so
// navigating between Manager sections (which remounts screens) never asks again during the same browser session.
let sessionUnlocked = Platform.OS !== "web";

interface Ctx {
  soundOn: boolean;
  unlocked: boolean;
  /** Called from a user tap: plays the alert once (unlocks audio on web) and turns sound on. */
  enable: () => void;
  toggle: () => void;
  /** Most recent genuinely new pending order (for the visual banner); cleared by dismiss(). */
  fresh: Order | null;
  dismiss: () => void;
}

const SoundCtx = createContext<Ctx>({ soundOn: false, unlocked: false, enable: () => {}, toggle: () => {}, fresh: null, dismiss: () => {} });
export const useStaffSound = () => useContext(SoundCtx);

/** One shared alert player for the whole staff area: rings immediately for each NEW pending order, then every 20 s
 *  while at least one order is still waiting in NOUVELLES; stops as soon as it is accepted/refused or sound is muted. */
export function StaffSoundProvider({ children, active }: { children: React.ReactNode; active: boolean }) {
  const player = useAudioPlayer(ALERT);
  const [soundOn, setSoundOn] = useState(true);
  const [unlocked, setUnlocked] = useState(sessionUnlocked);
  const [fresh, setFresh] = useState<Order | null>(null);
  const known = useRef<Set<string> | null>(null);
  const freshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { data } = useActiveOrders(active ? 3000 : 0);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY).then((v) => { if (v === "0") setSoundOn(false); }).catch(() => {});
  }, []);

  const ring = useCallback(() => {
    try {
      Promise.resolve(player.seekTo(0)).catch(() => {});
      Promise.resolve(player.play()).catch(() => {});
    } catch {}
  }, [player]);

  const enable = useCallback(() => {
    ring(); // inside the user gesture -> unlocks the media element on web
    sessionUnlocked = true;
    setUnlocked(true);
    setSoundOn(true);
    AsyncStorage.setItem(STORAGE_KEY, "1").catch(() => {});
  }, [ring]);

  const toggle = useCallback(() => {
    if (!sessionUnlocked) return enable();
    setSoundOn((v) => {
      AsyncStorage.setItem(STORAGE_KEY, v ? "0" : "1").catch(() => {});
      if (v) { try { player.pause(); } catch {} }
      return !v;
    });
  }, [enable, player]);

  // New-order detection: only orders never seen in this session ring; polling/refresh of known orders never does.
  useEffect(() => {
    if (!data || !active) return;
    const pending = data.filter((o) => o.status === "pending" && !o.legacy);
    if (known.current === null) {
      known.current = new Set(pending.map((o) => o.id));
      return;
    }
    const newOnes = pending.filter((o) => !known.current!.has(o.id));
    pending.forEach((o) => known.current!.add(o.id));
    if (newOnes.length) {
      setFresh(newOnes[0]);
      if (soundOn && unlocked) ring();
      if (freshTimer.current) clearTimeout(freshTimer.current);
      freshTimer.current = setTimeout(() => setFresh(null), 8000);
    }
  }, [data, active, soundOn, unlocked, ring]);

  // Reminder every 20 s while a NEW (un-accepted, same-day) order is waiting; stops on accept / mute.
  const waiting = useMemo(() => (data ?? []).filter((o) => o.status === "pending" && !o.legacy && !isScheduledLater(o)).length, [data]);
  useEffect(() => {
    if (!active || !soundOn || !unlocked || waiting === 0) return;
    const iv = setInterval(ring, REPEAT_MS);
    return () => clearInterval(iv);
  }, [active, soundOn, unlocked, waiting, ring]);

  const value = useMemo<Ctx>(() => ({ soundOn, unlocked, enable, toggle, fresh, dismiss: () => setFresh(null) }), [soundOn, unlocked, enable, toggle, fresh]);
  return <SoundCtx.Provider value={value}>{children}</SoundCtx.Provider>;
}
