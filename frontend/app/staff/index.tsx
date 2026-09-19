import React, { useMemo, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, useWindowDimensions, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import Animated, { FadeInDown, FadeOutUp } from "react-native-reanimated";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useActiveOrders } from "@/src/api";
import { useStaff } from "@/src/staff-auth";
import { useStaffSound } from "@/src/staff-sound";
import { FirstDeliveryControl } from "@/src/components/first-delivery";
import { Empty, FONT_DISPLAY, FONT_TEXT } from "@/src/components/ui";
import { OrderCard, OrderDetail, isScheduledLater } from "@/src/components/staff-order";
import type { StringKey } from "@/src/i18n";

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
  const wide = width >= 900;
  // Larger cards with every action inline: 1 column on phones, 2 on tablets/laptops, 3 on very wide screens
  const cols = width >= 1500 ? 3 : width >= 860 ? 2 : 1;
  const { data, isLoading } = useActiveOrders(3000);
  const orders = useMemo(() => data ?? [], [data]);
  const [filter, setFilter] = useState<Filter>("new");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Sound + new-order detection are shared for the whole staff area (see src/staff-sound.tsx)
  const { soundOn, unlocked: soundUnlocked, enable: unlockSound, toggle: toggleSound, fresh: alert, dismiss: dismissAlert } = useStaffSound();

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
  const selected = orders.find((o) => o.id === selectedId);
  const cardWidth = cols === 1 ? "100%" : cols === 2 ? "49%" : "32.4%";

  return (
    <View style={styles.screen}>
      {/* Header: back · title · sound · lock, then the full navigation row */}
      <View style={[styles.header, { paddingTop: insets.top + 6 }]}>
        <View style={styles.headerRow}>
          <Pressable testID="staff-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)/more"))} style={styles.iconBtn}><Feather name="arrow-left" size={20} color={colors.onSurface} /></Pressable>
          <View style={{ flexShrink: 1 }}>
            <Text style={styles.title} testID="staff-dashboard-title" numberOfLines={1}>{t("dashboard")}</Text>
            <Text style={styles.subtitle} numberOfLines={1}>{label}</Text>
          </View>
          <View style={{ flex: 1 }} />
          <Pressable testID="staff-sound-toggle" onPress={toggleSound} style={[styles.iconBtn, soundOn && soundUnlocked && styles.iconBtnOn]}>
            <Feather name={soundOn && soundUnlocked ? "volume-2" : "volume-x"} size={20} color={soundOn && soundUnlocked ? colors.onBrandPrimary : colors.onSurface} />
          </Pressable>
          <Pressable testID="staff-lock" onPress={() => { lock(); router.replace("/(tabs)/more"); }} style={styles.iconBtn}><Feather name="lock" size={18} color={colors.onSurface} /></Pressable>
        </View>
        {/* Navigation: always its own full-width row that WRAPS – every entry (incl. Administration) stays visible */}
        <NavRow role={role} />
      </View>

      {/* Sound must be enabled by a tap on web browsers (autoplay policy) – one clear button, once per session */}
      {soundOn && !soundUnlocked ? (
        <Pressable testID="staff-sound-enable" onPress={unlockSound} style={styles.soundBanner}>
          <Feather name="volume-2" size={20} color={colors.onWarning} />
          <Text style={styles.soundBannerText}>{t("enableSound")}</Text>
          <View style={styles.soundBannerBtn}><Text style={styles.soundBannerBtnText}>{t("enableSound").split(" ")[0].toUpperCase()}</Text></View>
        </Pressable>
      ) : null}

      {/* Alert banner */}
      {alert ? (
        <Animated.View entering={FadeInDown} exiting={FadeOutUp} style={styles.alert} testID="new-order-alert">
          <Feather name="bell" size={22} color={colors.onBrandPrimary} />
          <Text style={styles.alertText}>{t("orderReceived")} #{alert.order_number} · {alert.customer.first_name} · {alert.type === "pickup" ? t("pickup") : t("delivery")}{isScheduledLater(alert) ? ` · ${t("scheduled").toUpperCase()} ${alert.requested_date} ${alert.requested_time}` : ""}</Text>
          <Pressable testID="new-order-alert-open" onPress={() => { setFilter(isScheduledLater(alert) ? "scheduled" : "new"); dismissAlert(); }} style={styles.alertBtn}><Text style={styles.alertBtnText}>{t("newOrders").toUpperCase()}</Text></Pressable>
        </Animated.View>
      ) : null}

      {/* Filters + history + (manager) first-delivery control share one compact strip on wide screens */}
      <View style={[styles.toolbar, wide && { flexDirection: "row", alignItems: "center" }]}>
        <View style={[styles.segment, wide && { flex: 1, marginTop: 0 }]} testID="staff-filters">
          {(["new", "progress", "scheduled"] as Filter[]).map((f) => {
            const on = filter === f;
            const lbl = f === "new" ? t("newOrders") : f === "scheduled" ? t("scheduled") : t("inProgress");
            const alertF = (f === "new" && counts.new > 0) || (f === "scheduled" && counts.scheduledPending > 0);
            return (
              <Pressable key={f} testID={`staff-filter-${f}`} onPress={() => setFilter(f)} style={[styles.segBtn, on && styles.segBtnOn, alertF && !on && styles.segBtnAlert]}>
                <Text style={[styles.segText, !wide && styles.segTextSmall, on && styles.segTextOn]} numberOfLines={1} adjustsFontSizeToFit>{lbl.toUpperCase()}</Text>
                <View style={[styles.segCount, on && styles.segCountOn, alertF && !on && styles.segCountAlert]}><Text style={[styles.segCountText, (on || alertF) && styles.segCountTextOn]}>{counts[f]}</Text></View>
              </Pressable>
            );
          })}
          <Pressable testID="staff-filter-done" onPress={() => setFilter("done")} style={[styles.segBtn, styles.segBtnDone, filter === "done" && styles.segBtnOn]}>
            <Feather name="archive" size={16} color={filter === "done" ? colors.onSurfaceInverse : colors.muted} />
            <Text style={[styles.segText, styles.segTextSmall, filter === "done" && styles.segTextOn]} numberOfLines={1}>{wide ? `${t("history").toUpperCase()} · ${counts.done}` : counts.done}</Text>
          </Pressable>
        </View>
        {role === "manager" ? <View style={wide ? { width: 360 } : undefined}><FirstDeliveryControl /></View> : null}
      </View>

      {isLoading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brandPrimary} size="large" /></View>
      ) : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={[styles.grid, { paddingBottom: insets.bottom + 24 }]}>
          {list.length === 0 ? <View style={{ width: "100%" }}><Empty icon="inbox" title={t("noActiveOrders")} /></View> : null}
          {list.map((o) => (
            <View key={o.id} style={{ width: cardWidth }}>
              <OrderCard order={o} selected={selected?.id === o.id} onPress={() => setSelectedId(o.id)} />
            </View>
          ))}
        </ScrollView>
      )}
      {/* Full detail (custom time, reject, delay, cancel, print, receipt) opens on demand */}
      <Modal visible={!!selectedId && !!selected} animationType="slide" onRequestClose={() => setSelectedId(null)} presentationStyle="pageSheet">
        <View style={[styles.modal, { paddingTop: insets.top }]}>
          {selected ? <View style={styles.modalInner}><OrderDetail order={selected} onClose={() => setSelectedId(null)} /></View> : null}
        </View>
      </Modal>
    </View>
  );
}

function NavRow({ role }: { role: string | null }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  return (
    <View style={styles.navRow}>
      {NAV.filter((n) => !n.manager || role === "manager").map((n) => (
        <Pressable key={n.testID} testID={n.testID} onPress={() => router.push(n.href as any)} style={[styles.navBtn, n.testID === "staff-go-admin" && styles.navBtnAdmin]}>
          <Feather name={n.icon} size={16} color={n.testID === "staff-go-admin" ? colors.onSurfaceInverse : colors.onSurface} />
          <Text style={[styles.navText, n.testID === "staff-go-admin" && { color: colors.onSurfaceInverse }]}>{t(n.label)}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  header: { gap: 6, paddingBottom: 8, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12 },
  title: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  subtitle: { fontFamily: FONT_TEXT, fontSize: 11, color: colors.muted },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  iconBtnOn: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  navRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, paddingHorizontal: 12, alignItems: "center" },
  navBtnAdmin: { backgroundColor: colors.surfaceInverse, borderColor: colors.surfaceInverse },
  navBtn: { flexDirection: "row", alignItems: "center", gap: 6, height: 40, paddingHorizontal: 14, borderRadius: 20, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  navText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.onSurface },
  soundBanner: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.warning, padding: 12, marginHorizontal: 12, marginTop: 10, borderRadius: 14 },
  soundBannerText: { flex: 1, fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "800", color: colors.onWarning },
  soundBannerBtn: { backgroundColor: colors.onWarning, paddingHorizontal: 14, height: 40, borderRadius: 10, justifyContent: "center" },
  soundBannerBtnText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "900", color: colors.warning },
  alert: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.brandPrimary, padding: 14, marginHorizontal: 12, marginTop: 10, borderRadius: 14 },
  alertText: { flex: 1, fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.onBrandPrimary },
  alertBtn: { backgroundColor: colors.onBrandPrimary, paddingHorizontal: 14, height: 36, borderRadius: 10, justifyContent: "center" },
  alertBtnText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "800", color: colors.brandPrimary },
  toolbar: { gap: 8, paddingHorizontal: 12, paddingTop: 10, paddingBottom: 4 },
  segment: { flexDirection: "row", gap: 6, padding: 4, borderRadius: 16, backgroundColor: colors.surfaceTertiary },
  segBtn: { flex: 1, flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2, height: 56, borderRadius: 12, paddingHorizontal: 4 },
  segBtnDone: { flex: 0.7, minWidth: 44 },
  segTextSmall: { fontSize: 10, letterSpacing: 0.2 },
  segCountAlert: { backgroundColor: colors.brandPrimary },
  segBtnOn: { backgroundColor: colors.surfaceInverse },
  segBtnAlert: { borderWidth: 2, borderColor: colors.brandPrimary, backgroundColor: colors.brandSoft },
  segText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "900", color: colors.onSurface, letterSpacing: 0.6 },
  segTextOn: { color: colors.onSurfaceInverse },
  segCount: { minWidth: 26, height: 22, borderRadius: 11, paddingHorizontal: 8, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  segCountOn: { backgroundColor: colors.brandPrimary },
  segCountText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "800", color: colors.onSurface },
  segCountTextOn: { color: colors.onBrandPrimary },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  grid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", rowGap: 12, padding: 12 },
  modal: { flex: 1, backgroundColor: colors.surface, alignItems: "center" },
  modalInner: { flex: 1, width: "100%", maxWidth: 720 },
}));
