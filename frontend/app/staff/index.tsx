import React, { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, useWindowDimensions, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import { useAudioPlayer } from "expo-audio";
import Animated, { FadeInDown, FadeOutUp } from "react-native-reanimated";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useActiveOrders } from "@/src/api";
import { useStaff } from "@/src/staff-auth";
import { FirstDeliveryControl } from "@/src/components/first-delivery";
import { Empty, FONT_DISPLAY, FONT_TEXT } from "@/src/components/ui";
import { OrderCard, OrderDetail, isScheduledLater } from "@/src/components/staff-order";
import type { Order } from "@/src/types";
import type { StringKey } from "@/src/i18n";

const ALERT = require("../../assets/sounds/alert.wav");
type Filter = "new" | "scheduled" | "progress" | "done";
type NavItem = { testID: string; href: string; icon: React.ComponentProps<typeof Feather>["name"]; label: StringKey; manager?: boolean };
const NAV: NavItem[] = [
  { testID: "staff-go-kitchen", href: "/staff/kitchen", icon: "coffee", label: "kitchen" },
  { testID: "staff-go-phone-orders", href: "/phone-orders", icon: "phone", label: "phoneOrders" },
  { testID: "staff-go-customers", href: "/staff/customers", icon: "users", label: "customers" },
  { testID: "staff-go-closing", href: "/staff/closing", icon: "bar-chart-2", label: "closing", manager: true },
  { testID: "staff-go-admin", href: "/staff/admin", icon: "settings", label: "admin", manager: true },
];

export default function StaffDashboard() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const { lock, role, label } = useStaff();
  const { width } = useWindowDimensions();
  const twoCol = width >= 900;
  const { data, isLoading } = useActiveOrders(3000);
  const orders = useMemo(() => data ?? [], [data]);
  const [filter, setFilter] = useState<Filter>("new");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [soundOn, setSoundOn] = useState(true);
  const [alert, setAlert] = useState<Order | null>(null);
  const player = useAudioPlayer(ALERT);
  const known = useRef<Set<string> | null>(null);

  // New order detection -> visual + audio alert
  useEffect(() => {
    if (!data) return;
    const pendingIds = data.filter((o) => o.status === "pending").map((o) => o.id);
    if (known.current === null) {
      known.current = new Set(pendingIds);
      return;
    }
    const fresh = data.find((o) => o.status === "pending" && !o.legacy && !known.current!.has(o.id));
    pendingIds.forEach((id) => known.current!.add(id));
    if (fresh) {
      setAlert(fresh);
      if (soundOn) {
        // Safari/iPad may reject autoplay: never let audio break the dashboard or order sync
        try {
          Promise.resolve(player.seekTo(0)).catch(() => {});
          Promise.resolve(player.play()).catch(() => {});
        } catch {}
      }
      const tmr = setTimeout(() => setAlert(null), 8000);
      return () => clearTimeout(tmr);
    }
  }, [data, soundOn, player]);

  // Operational lists only contain live orders; pre-go-live test data (legacy) and finished orders live in Historique
  const live = useMemo(() => orders.filter((o) => !o.legacy), [orders]);
  const counts = useMemo(() => ({
    new: live.filter((o) => o.status === "pending" && !isScheduledLater(o)).length,
    scheduled: live.filter((o) => isScheduledLater(o) && !["completed", "cancelled"].includes(o.status)).length,
    scheduledPending: live.filter((o) => isScheduledLater(o) && o.status === "pending").length,
    progress: live.filter((o) => !["pending", "completed", "cancelled"].includes(o.status) && !isScheduledLater(o)).length,
    done: orders.filter((o) => o.legacy || ["completed", "cancelled"].includes(o.status)).length,
  }), [orders, live]);

  const list = orders
    .filter((o) =>
      filter === "new" ? !o.legacy && o.status === "pending" && !isScheduledLater(o)
        : filter === "scheduled" ? !o.legacy && isScheduledLater(o) && !["completed", "cancelled"].includes(o.status)
          : filter === "progress" ? !o.legacy && !["pending", "completed", "cancelled"].includes(o.status) && !isScheduledLater(o)
            : o.legacy || ["completed", "cancelled"].includes(o.status),
    )
    .sort((a, b) => (filter === "scheduled" ? (a.scheduled_for || "").localeCompare(b.scheduled_for || "") : 0));
  const selected = orders.find((o) => o.id === selectedId) ?? (twoCol ? list[0] : undefined);

  return (
    <View style={styles.screen}>
      {/* Header: title + sound + lock. Navigation shortcuts live in their own labelled row below. */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <View style={styles.headerRow}>
          <Pressable testID="staff-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)/more"))} style={styles.iconBtn}><Feather name="arrow-left" size={20} color={colors.onSurface} /></Pressable>
          <View style={{ flex: 1 }}>
            <Text style={styles.title} testID="staff-dashboard-title" numberOfLines={1}>{t("dashboard")}</Text>
            <Text style={styles.subtitle} numberOfLines={1}>{label}</Text>
          </View>
          <Pressable testID="staff-sound-toggle" onPress={() => setSoundOn((v) => !v)} style={[styles.iconBtn, soundOn && styles.iconBtnOn]}>
            <Feather name={soundOn ? "volume-2" : "volume-x"} size={20} color={soundOn ? colors.onBrandPrimary : colors.onSurface} />
          </Pressable>
          <Pressable testID="staff-lock" onPress={() => { lock(); router.replace("/(tabs)/more"); }} style={styles.iconBtn}><Feather name="lock" size={18} color={colors.onSurface} /></Pressable>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.navRow}>
          {NAV.filter((n) => !n.manager || role === "manager").map((n) => (
            <Pressable key={n.testID} testID={n.testID} onPress={() => router.push(n.href as any)} style={styles.navBtn}>
              <Feather name={n.icon} size={16} color={colors.onSurface} />
              <Text style={styles.navText}>{t(n.label)}</Text>
            </Pressable>
          ))}
        </ScrollView>
      </View>

      {/* Alert banner */}
      {alert ? (
        <Animated.View entering={FadeInDown} exiting={FadeOutUp} style={styles.alert} testID="new-order-alert">
          <Feather name="bell" size={22} color={colors.onBrandPrimary} />
          <Text style={styles.alertText}>{t("orderReceived")} #{alert.order_number} · {alert.customer.first_name} · {alert.type === "pickup" ? t("pickup") : t("delivery")}{isScheduledLater(alert) ? ` · ${t("scheduled").toUpperCase()} ${alert.requested_date} ${alert.requested_time}` : ""}</Text>
          <Pressable testID="new-order-alert-open" onPress={() => { setFilter(isScheduledLater(alert) ? "scheduled" : "new"); setSelectedId(alert.id); setAlert(null); }} style={styles.alertBtn}><Text style={styles.alertBtnText}>{t("edit").toUpperCase()}</Text></Pressable>
        </Animated.View>
      ) : null}

      {/* Filters: full-width segmented control, then (manager) the collapsible first-delivery card */}
      <View style={styles.segment} testID="staff-filters">
        {(["new", "progress", "scheduled"] as Filter[]).map((f) => {
          const on = filter === f;
          const lbl = f === "new" ? t("newOrders") : f === "scheduled" ? t("scheduled") : t("inProgress");
          const alert = (f === "new" && counts.new > 0) || (f === "scheduled" && counts.scheduledPending > 0);
          return (
            <Pressable key={f} testID={`staff-filter-${f}`} onPress={() => setFilter(f)} style={[styles.segBtn, on && styles.segBtnOn, alert && !on && styles.segBtnAlert]}>
              <Text style={[styles.segText, on && styles.segTextOn]} numberOfLines={1}>{lbl.toUpperCase()}</Text>
              <View style={[styles.segCount, on && styles.segCountOn, alert && !on && styles.segCountAlert]}><Text style={[styles.segCountText, (on || alert) && styles.segCountTextOn]}>{counts[f]}</Text></View>
            </Pressable>
          );
        })}
      </View>
      <View style={styles.secondaryRow}>
        <Pressable testID="staff-filter-done" onPress={() => setFilter("done")} style={[styles.doneLink, filter === "done" && styles.doneLinkOn]}>
          <Feather name="archive" size={14} color={filter === "done" ? colors.onSurfaceInverse : colors.muted} />
          <Text style={[styles.doneLinkText, filter === "done" && { color: colors.onSurfaceInverse }]}>{t("history")} · {counts.done}</Text>
        </Pressable>
      </View>
      {role === "manager" ? <FirstDeliveryControl /> : null}

      {isLoading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brandPrimary} size="large" /></View>
      ) : (
        <View style={{ flex: 1, flexDirection: twoCol ? "row" : "column" }}>
          <ScrollView style={twoCol ? styles.leftPane : { flex: 1 }} contentContainerStyle={{ padding: 12, gap: 10, paddingBottom: insets.bottom + 24 }}>
            {list.length === 0 ? <Empty icon="inbox" title={t("noActiveOrders")} /> : null}
            {list.map((o) => <OrderCard key={o.id} order={o} selected={selected?.id === o.id} onPress={() => setSelectedId(o.id)} />)}
          </ScrollView>
          {twoCol ? (
            <View style={styles.rightPane}>
              {selected ? <OrderDetail order={selected} /> : <Empty icon="mouse-pointer" title={t("selectOrder")} />}
            </View>
          ) : (
            <Modal visible={!!selectedId && !!selected} animationType="slide" onRequestClose={() => setSelectedId(null)} presentationStyle="pageSheet">
              <View style={[styles.modal, { paddingTop: insets.top }]}>{selected ? <OrderDetail order={selected} onClose={() => setSelectedId(null)} /> : null}</View>
            </Modal>
          )}
        </View>
      )}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  header: { gap: 8, paddingBottom: 10, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12 },
  title: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
  subtitle: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  iconBtnOn: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  navRow: { gap: 8, paddingHorizontal: 12 },
  navBtn: { flexDirection: "row", alignItems: "center", gap: 6, height: 40, paddingHorizontal: 14, borderRadius: 20, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  navText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.onSurface },
  alert: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.brandPrimary, padding: 14, marginHorizontal: 12, marginTop: 10, borderRadius: 14 },
  alertText: { flex: 1, fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.onBrandPrimary },
  alertBtn: { backgroundColor: colors.onBrandPrimary, paddingHorizontal: 14, height: 36, borderRadius: 10, justifyContent: "center" },
  alertBtnText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "800", color: colors.brandPrimary },
  segment: { flexDirection: "row", gap: 6, marginHorizontal: 12, marginTop: 12, padding: 4, borderRadius: 16, backgroundColor: colors.surfaceTertiary },
  segBtn: { flex: 1, flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2, height: 60, borderRadius: 12, paddingHorizontal: 4 },
  segCountAlert: { backgroundColor: colors.brandPrimary },
  secondaryRow: { flexDirection: "row", justifyContent: "flex-end", paddingHorizontal: 12, paddingVertical: 6 },
  doneLink: { flexDirection: "row", alignItems: "center", gap: 6, height: 32, paddingHorizontal: 12, borderRadius: 16 },
  doneLinkOn: { backgroundColor: colors.surfaceInverse },
  doneLinkText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "800", color: colors.muted },
  segBtnOn: { backgroundColor: colors.surfaceInverse },
  segBtnAlert: { borderWidth: 2, borderColor: colors.brandPrimary, backgroundColor: colors.brandSoft },
  segText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "900", color: colors.onSurface, letterSpacing: 0.6 },
  segTextOn: { color: colors.onSurfaceInverse },
  segCount: { minWidth: 26, height: 22, borderRadius: 11, paddingHorizontal: 8, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  segCountOn: { backgroundColor: colors.brandPrimary },
  segCountText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "800", color: colors.onSurface },
  segCountTextOn: { color: colors.onBrandPrimary },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  leftPane: { width: "52%", borderRightWidth: 1, borderRightColor: colors.border },
  rightPane: { flex: 1, backgroundColor: colors.surface },
  modal: { flex: 1, backgroundColor: colors.surface },
}));
