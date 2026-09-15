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
import { Chip, Empty, FONT_DISPLAY, FONT_TEXT } from "@/src/components/ui";
import { OrderCard, OrderDetail } from "@/src/components/staff-order";
import type { Order } from "@/src/types";

const ALERT = require("../../assets/sounds/alert.wav");
type Filter = "new" | "progress" | "done";

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
    const fresh = data.find((o) => o.status === "pending" && !known.current!.has(o.id));
    pendingIds.forEach((id) => known.current!.add(id));
    if (fresh) {
      setAlert(fresh);
      if (soundOn) {
        try {
          player.seekTo(0);
          player.play();
        } catch {}
      }
      const tmr = setTimeout(() => setAlert(null), 8000);
      return () => clearTimeout(tmr);
    }
  }, [data, soundOn, player]);

  const counts = useMemo(() => ({
    new: orders.filter((o) => o.status === "pending").length,
    progress: orders.filter((o) => !["pending", "completed", "cancelled"].includes(o.status)).length,
    done: orders.filter((o) => ["completed", "cancelled"].includes(o.status)).length,
  }), [orders]);

  const list = orders.filter((o) =>
    filter === "new" ? o.status === "pending" : filter === "progress" ? !["pending", "completed", "cancelled"].includes(o.status) : ["completed", "cancelled"].includes(o.status),
  );
  const selected = orders.find((o) => o.id === selectedId) ?? (twoCol ? list[0] : undefined);

  return (
    <View style={styles.screen}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Pressable testID="staff-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)/more"))} style={styles.iconBtn}><Feather name="arrow-left" size={20} color={colors.onSurface} /></Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.title} testID="staff-dashboard-title" numberOfLines={1}>{t("dashboard")}</Text>
          <Text style={styles.subtitle} numberOfLines={1}>{label} · iPhone · Android · Web · Téléphone</Text>
        </View>
        <Pressable testID="staff-sound-toggle" onPress={() => setSoundOn((v) => !v)} style={[styles.iconBtn, soundOn && styles.iconBtnOn]}>
          <Feather name={soundOn ? "volume-2" : "volume-x"} size={20} color={soundOn ? colors.onBrandPrimary : colors.onSurface} />
        </Pressable>
        <Pressable testID="staff-go-kitchen" onPress={() => router.push("/staff/kitchen")} style={styles.iconBtn}><Feather name="coffee" size={20} color={colors.onSurface} /></Pressable>
        <Pressable testID="staff-go-phone-orders" onPress={() => router.push("/phone-orders")} style={styles.iconBtn}><Feather name="phone" size={20} color={colors.onSurface} /></Pressable>
        <Pressable testID="staff-go-customers" onPress={() => router.push("/staff/customers")} style={styles.iconBtn}><Feather name="users" size={20} color={colors.onSurface} /></Pressable>
        {role === "manager" ? <Pressable testID="staff-go-closing" onPress={() => router.push("/staff/closing")} style={styles.iconBtn}><Feather name="bar-chart-2" size={20} color={colors.onSurface} /></Pressable> : null}
        {role === "manager" ? <Pressable testID="staff-go-admin" onPress={() => router.push("/staff/admin")} style={styles.iconBtn}><Feather name="settings" size={20} color={colors.onSurface} /></Pressable> : null}
        <Pressable testID="staff-lock" onPress={() => { lock(); router.replace("/(tabs)/more"); }} style={styles.iconBtn}><Feather name="lock" size={18} color={colors.onSurface} /></Pressable>
      </View>

      {/* Alert banner */}
      {alert ? (
        <Animated.View entering={FadeInDown} exiting={FadeOutUp} style={styles.alert} testID="new-order-alert">
          <Feather name="bell" size={22} color={colors.onBrandPrimary} />
          <Text style={styles.alertText}>{t("orderReceived")} #{alert.order_number} · {alert.customer.first_name} · {alert.type === "pickup" ? t("pickup") : t("delivery")}</Text>
          <Pressable testID="new-order-alert-open" onPress={() => { setFilter("new"); setSelectedId(alert.id); setAlert(null); }} style={styles.alertBtn}><Text style={styles.alertBtnText}>{t("edit").toUpperCase()}</Text></Pressable>
        </Animated.View>
      ) : null}

      {/* Filters */}
      <View style={styles.chipRow}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
          <Chip label={`${t("newOrders")} (${counts.new})`} selected={filter === "new"} onPress={() => setFilter("new")} testID="staff-filter-new" />
          <Chip label={`${t("inProgress")} (${counts.progress})`} selected={filter === "progress"} onPress={() => setFilter("progress")} testID="staff-filter-progress" />
          <Chip label={`${t("done")} (${counts.done})`} selected={filter === "done"} onPress={() => setFilter("done")} testID="staff-filter-done" />
        </ScrollView>
      </View>

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
  header: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingBottom: 10, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  title: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
  subtitle: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  iconBtnOn: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  alert: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.brandPrimary, padding: 14, marginHorizontal: 12, marginTop: 10, borderRadius: 14 },
  alertText: { flex: 1, fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.onBrandPrimary },
  alertBtn: { backgroundColor: colors.onBrandPrimary, paddingHorizontal: 14, height: 36, borderRadius: 10, justifyContent: "center" },
  alertBtnText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "800", color: colors.brandPrimary },
  chipRow: { height: 56, justifyContent: "center" },
  chips: { gap: 8, paddingHorizontal: 12, alignItems: "center" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  leftPane: { width: "34%", borderRightWidth: 1, borderRightColor: colors.border },
  rightPane: { flex: 1, backgroundColor: colors.surface },
  modal: { flex: 1, backgroundColor: colors.surface },
}));
