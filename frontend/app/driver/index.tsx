import React from "react";
import { ActivityIndicator, Linking, Platform, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import { makeStyles, useTheme } from "@/src/theme";
import { statusLabel, useI18n } from "@/src/i18n";
import { useDriverAction, useDriverOrders } from "@/src/api";
import { useStaff } from "@/src/staff-auth";
import { chf, fmtTime, statusTone } from "@/src/format";
import { Badge, Button, Empty, FONT_DISPLAY, FONT_TEXT, useToast } from "@/src/components/ui";
import type { Order } from "@/src/types";

/** /driver – phone screen for Livreur 1/2/3. Shows ONLY the deliveries assigned to the logged-in driver number.
 * `?o=<orderId>` (from the ticket QR) scrolls that order to the top – still requires the driver login. */
export default function DriverScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const toast = useToast();
  const { o: focusId } = useLocalSearchParams<{ o?: string }>();
  const { ready, unlocked, isDriver, driverName, lock } = useStaff();
  const { data, isLoading, isError, refetch, isRefetching } = useDriverOrders();
  const act = useDriverAction();

  if (!ready) return <View style={[styles.screen, styles.center]}><ActivityIndicator color={colors.brandPrimary} /></View>;
  if (!unlocked) return <Redirect href="/staff/login" />;
  if (!isDriver) return <Redirect href="/staff" />;

  const orders = [...(data ?? [])].sort((a, b) => (a.id === focusId ? -1 : b.id === focusId ? 1 : 0));
  const active = orders.filter((o) => !["delivered", "completed"].includes(o.status));
  const done = orders.filter((o) => ["delivered", "completed"].includes(o.status));

  const run = async (o: Order, action: "pickup" | "depart" | "delivered" | "collect", body?: object) => {
    try {
      await act.mutateAsync({ id: o.id, action, body });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };
  const openMap = (o: Order) => {
    const a = o.address!;
    const q = encodeURIComponent(`${a.street} ${a.number}, ${a.npa} ${a.city}`);
    Linking.openURL(Platform.OS === "ios" ? `maps://?daddr=${q}` : `https://www.google.com/maps/dir/?api=1&destination=${q}`).catch(() => Linking.openURL(`https://www.google.com/maps/search/?api=1&query=${q}`));
  };

  return (
    <View style={styles.screen}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <View style={{ flex: 1 }}>
          <Text style={styles.title} testID="driver-title">{driverName}</Text>
          <Text style={styles.subtitle}>{t("driverScreen")} · {active.length}</Text>
        </View>
        <Pressable testID="driver-lock" onPress={() => { lock(); router.replace("/staff/login"); }} style={styles.iconBtn}><Feather name="log-out" size={18} color={colors.onSurfaceInverse} /></Pressable>
      </View>
      {isLoading ? <View style={styles.center}><ActivityIndicator color={colors.brandPrimary} size="large" /></View> : (
        <ScrollView contentContainerStyle={{ padding: 14, gap: 14, paddingBottom: insets.bottom + 30 }} refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.brandPrimary} />}>
          {isError ? <View style={styles.offline} testID="driver-offline"><Feather name="wifi-off" size={16} color={colors.onError} /><Text style={styles.offlineText}>{t("loadError")}</Text></View> : null}
          {active.length === 0 ? <Empty icon="truck" title={t("noDeliveries")} /> : null}
          {active.map((o) => <DeliveryCard key={o.id} o={o} focus={o.id === focusId} onAction={run} onMap={openMap} busy={act.isPending} />)}
          {done.length ? <Text style={styles.doneTitle} testID="driver-done-today">{t("doneToday")} · {done.length}</Text> : null}
          {done.map((o) => <DeliveryCard key={o.id} o={o} onAction={run} onMap={openMap} busy={act.isPending} compact />)}
        </ScrollView>
      )}
    </View>
  );
}

function DeliveryCard({ o, focus, onAction, onMap, busy, compact }: { o: Order; focus?: boolean; onAction: (o: Order, a: "pickup" | "depart" | "delivered" | "collect", b?: object) => void; onMap: (o: Order) => void; busy: boolean; compact?: boolean }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const a = o.address!;
  const method = o.collection_method ?? (o.payment_method === "terminal" ? "terminal" : "cash");
  const paid = o.payment_collected || method === "none";
  return (
    <View style={[styles.card, focus && styles.cardFocus, compact && { opacity: 0.75 }]} testID={`driver-order-${o.id}`}>
      <View style={styles.rowBetween}>
        <Text style={styles.num}>#{o.order_number}</Text>
        <View style={{ alignItems: "flex-end" }}>
          <Text style={styles.time} testID={`driver-time-${o.id}`}>{fmtTime(o.estimated_ready_at)}</Text>
          <Text style={styles.hint}>{t("confirmedDelivery")}</Text>
        </View>
      </View>
      <Badge label={statusLabel(o.status, o.type, t)} tone={statusTone(o.status)} />
      {o.age_required ? <View style={styles.ageBox} testID={`driver-age-${o.id}`}><Feather name="alert-triangle" size={20} color={colors.onWarning} /><Text style={styles.ageText}>{t("ageCheckRequired")}: {o.age_required}+ · {t("ageCheckHint")}</Text></View> : null}

      {/* Collection block */}
      <View style={[styles.payBox, paid ? { backgroundColor: colors.success } : method === "terminal" ? { backgroundColor: colors.surfaceInverse } : { backgroundColor: colors.brandPrimary }]} testID={`driver-pay-${o.id}`}>
        <Text style={styles.payText}>{paid ? t("nothingToCollect") : method === "terminal" ? `TERMINAL · ${chf(o.amount_due || o.total)}` : `${t("toCollect")}: ${chf(o.amount_due || o.total)}`}</Text>
        {!paid ? <Text style={styles.paySub}>{method === "terminal" ? t("payTerminal") : t("payCash")}</Text> : null}
      </View>

      <View style={{ gap: 2 }}>
        <Text style={styles.name}>{o.customer.first_name} {o.customer.last_name}</Text>
        <Pressable testID={`driver-call-${o.id}`} onPress={() => Linking.openURL(`tel:${o.customer.phone}`)}><Text style={styles.phone}>☎ {o.customer.phone}</Text></Pressable>
        <Text style={styles.addr}>{a.street} {a.number}</Text>
        <Text style={styles.addr}>{a.npa} {a.city}</Text>
        {a.instructions ? <Text style={styles.note}>ℹ {a.instructions}</Text> : null}
        {o.general_note ? <Text style={styles.note}>NOTE: {o.general_note}</Text> : null}
        <Text style={styles.hint}>{o.items.map((i) => `${i.quantity}x ${i.name.fr}${i.size ? ` ${i.size.label}` : ""}`).join(", ")} · {t("total")} {chf(o.total)}</Text>
      </View>
      <Button title={t("openMap")} icon="navigation" variant="outline" onPress={() => onMap(o)} testID={`driver-map-${o.id}`} />

      {/* Flow: Assigned → PARTI / EN LIVRAISON → payment confirmation → LIVRÉE */}
      {!compact && o.status !== "delivering" ? <Button title={t("departed")} size="xl" icon="truck" loading={busy} onPress={() => onAction(o, "depart")} testID={`driver-depart-${o.id}`} /> : null}
      {!paid ? <Button title={`${t("confirmCollected")} · ${chf(o.amount_due || o.total)}`} size={compact ? "md" : "lg"} icon="check-circle" variant={o.status === "delivering" ? "secondary" : "outline"} loading={busy} onPress={() => onAction(o, "collect", { method })} testID={`driver-collect-${o.id}`} /> : <Text style={[styles.hint, { color: colors.success, fontWeight: "800" }]}>✓ {t("collected")} {fmtTime(o.collected_at)}</Text>}
      {!compact && o.status === "delivering" ? <Button title={t("deliveredAction")} size="xl" icon="home" variant="success" loading={busy} onPress={() => onAction(o, "delivered")} testID={`driver-delivered-${o.id}`} /> : null}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 16, paddingBottom: 12, backgroundColor: colors.surfaceInverse },
  title: { fontFamily: FONT_DISPLAY, fontSize: 26, color: colors.onSurfaceInverse },
  subtitle: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.onSurfaceInverse, opacity: 0.8 },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.overlay, alignItems: "center", justifyContent: "center" },
  offline: { flexDirection: "row", gap: 8, alignItems: "center", backgroundColor: colors.error, borderRadius: 12, padding: 12 },
  offlineText: { fontFamily: FONT_TEXT, color: colors.onError, fontWeight: "700" },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 18, borderWidth: 1.5, borderColor: colors.border, padding: 16, gap: 12 },
  cardFocus: { borderColor: colors.brandPrimary, borderWidth: 3 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  num: { fontFamily: FONT_DISPLAY, fontSize: 36, color: colors.onSurface },
  time: { fontFamily: FONT_DISPLAY, fontSize: 30, color: colors.brandSecondary },
  hint: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  ageBox: { flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: colors.warning, borderRadius: 12, padding: 12 },
  ageText: { flex: 1, fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "900", color: colors.onWarning },
  payBox: { borderRadius: 14, padding: 14, alignItems: "center" },
  payText: { fontFamily: FONT_TEXT, fontSize: 20, fontWeight: "900", color: colors.onBrandPrimary, letterSpacing: 0.5 },
  paySub: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "700", color: colors.onBrandPrimary, opacity: 0.9, marginTop: 2 },
  name: { fontFamily: FONT_TEXT, fontSize: 20, fontWeight: "800", color: colors.onSurface },
  phone: { fontFamily: FONT_TEXT, fontSize: 18, fontWeight: "700", color: colors.brandPrimary, paddingVertical: 4 },
  addr: { fontFamily: FONT_TEXT, fontSize: 18, color: colors.onSurface, lineHeight: 24 },
  note: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "700", color: colors.warning, marginTop: 4 },
  doneTitle: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "800", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8, marginTop: 8 },
}));
