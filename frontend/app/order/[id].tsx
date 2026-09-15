import React from "react";
import { ActivityIndicator, ScrollView, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import Animated, { FadeIn } from "react-native-reanimated";
import { makeStyles, useTheme } from "@/src/theme";
import { statusLabel, useI18n } from "@/src/i18n";
import { useOrder } from "@/src/api";
import { chf, fmtTime, minutesUntil, statusTone } from "@/src/format";
import { Badge, Button, FONT_DISPLAY, FONT_TEXT, ScreenHeader } from "@/src/components/ui";
import { OrderTracker } from "@/src/components/order-tracker";
import { OrderLines } from "@/src/components/order-lines";

export default function OrderScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t, lang } = useI18n();
  const { data: o, isLoading } = useOrder(id);

  if (isLoading || !o) {
    return (
      <View style={[styles.screen, { alignItems: "center", justifyContent: "center" }]}>
        <ActivityIndicator color={colors.brandPrimary} size="large" />
      </View>
    );
  }

  const mins = minutesUntil(o.estimated_ready_at);
  const pending = o.status === "pending";
  const cancelled = o.status === "cancelled";
  const requested = o.requested_time && o.requested_time !== "asap" ? o.requested_time : null;

  return (
    <View style={styles.screen}>
      <ScreenHeader title={`${t("orderNumber")} #${o.order_number}`} subtitle={`${o.type === "pickup" ? t("pickup") : t("delivery")} · ${fmtTime(o.created_at)}`} testID="order-title" right={<Badge label={statusLabel(o.status, o.type, t)} tone={statusTone(o.status)} testID="order-status-badge" />} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: insets.bottom + 24, gap: 16 }}>
        {/* ETA hero */}
        <Animated.View entering={FadeIn} style={[styles.hero, pending && styles.heroPending, cancelled && styles.heroCancel]} testID="order-eta-card">
          {cancelled ? (
            <>
              <Feather name="x-circle" size={36} color={colors.onSurfaceInverse} />
              <Text style={styles.heroTitle}>{t("orderCancelled")}</Text>
              {o.reject_reason ? <Text style={styles.heroSub}>{o.reject_reason}</Text> : null}
            </>
          ) : pending ? (
            <>
              <ActivityIndicator color={colors.onSurfaceInverse} />
              <Text style={styles.heroTitle}>{t("waitingConfirmation")}</Text>
              {requested ? <Text style={styles.heroSub}>{o.type === "pickup" ? t("requestedPickup") : t("requestedDelivery")}: {requested}</Text> : <Text style={styles.heroSub}>{t("asap")}</Text>}
            </>
          ) : (
            <>
              <Text style={styles.heroLabel}>{o.type === "pickup" ? t("acceptedReadyAt") : t("acceptedDeliveryAt")}</Text>
              <Text style={styles.heroTime} testID="order-eta-time">{fmtTime(o.estimated_ready_at)}</Text>
              {mins !== null && mins > 0 && !["ready", "picked_up", "delivered", "completed"].includes(o.status) ? <Text style={styles.heroSub}>≈ {mins} min</Text> : null}
              {o.time_changed && requested ? (
                <View style={styles.changed} testID="order-time-changed">
                  <Feather name="alert-circle" size={14} color={colors.onSurfaceInverse} />
                  <Text style={styles.changedText}>{t("timeChanged")} ({requested} → {fmtTime(o.estimated_ready_at)})</Text>
                </View>
              ) : null}
              {o.delay_minutes_total > 0 && !o.time_changed ? <Text style={styles.heroSub}>{t("delayNotice")}: +{o.delay_minutes_total} min</Text> : null}
            </>
          )}
        </Animated.View>

        {/* Tracker */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t("tracker")}</Text>
          <OrderTracker order={o} />
        </View>

        {/* Items */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t("items")}</Text>
          <OrderLines items={o.items} />
          {o.general_note ? <Text style={styles.note}>« {o.general_note} »</Text> : null}
          <View style={styles.divider} />
          {o.delivery_fee > 0 ? <Row label={t("deliveryFee")} value={chf(o.delivery_fee)} /> : null}
          <View style={styles.row}>
            <Text style={styles.totalLabel}>{t("total")}</Text>
            <Text style={styles.totalValue} testID="order-total">{chf(o.total)}</Text>
          </View>
          <Text style={styles.pay}>{o.payment_method === "pay_at_pickup" ? t("payAtPickup") : t("payAtDelivery")}</Text>
          {o.vat_breakdown?.length ? (
            <View style={styles.vatBox} testID="order-vat-breakdown">
              <Text style={styles.vatTitle}>{t("vatIncluded")}</Text>
              {o.vat_breakdown.map((g) => (
                <Text key={g.rate} style={styles.vatLine}>{t("vat")} {g.rate.toFixed(1)}% · {t("vatBase")} {chf(g.net)} · {t("vat")} {chf(g.vat)}</Text>
              ))}
            </View>
          ) : null}
        </View>

        {/* Delivery address */}
        {o.address ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t("delivery")}</Text>
            <Text style={styles.addr}>{o.address.street} {o.address.number}{"\n"}{o.address.npa} {o.address.city}</Text>
            {o.address.instructions ? <Text style={styles.note}>{o.address.instructions}</Text> : null}
          </View>
        ) : null}

        {/* Notifications */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t("notifications")}</Text>
          {[...o.notifications].reverse().map((n, i) => (
            <View key={i} style={styles.notif} testID={`notification-${n.event}`}>
              <View style={styles.notifDot} />
              <View style={{ flex: 1 }}>
                <Text style={styles.notifTitle}>{n.title[lang as "fr" | "de"] || n.title.fr}</Text>
                <Text style={styles.notifBody}>{n.body[lang as "fr" | "de"] || n.body.fr}</Text>
              </View>
              <Text style={styles.notifTime}>{fmtTime(n.created_at)}</Text>
            </View>
          ))}
        </View>

        <Button title={t("browseMenu")} variant="outline" onPress={() => router.replace("/(tabs)")} testID="order-back-to-menu" />
      </ScrollView>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  const styles = useStyles();
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  hero: { backgroundColor: colors.brandSecondary, borderRadius: 20, padding: 24, alignItems: "center", gap: 6 },
  heroPending: { backgroundColor: colors.brandTertiary },
  heroCancel: { backgroundColor: colors.error },
  heroLabel: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceInverse, opacity: 0.9, textAlign: "center" },
  heroTime: { fontFamily: FONT_DISPLAY, fontSize: 56, color: colors.onSurfaceInverse, lineHeight: 64 },
  heroTitle: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurfaceInverse, textAlign: "center" },
  heroSub: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceInverse, opacity: 0.9, textAlign: "center" },
  changed: { flexDirection: "row", gap: 6, alignItems: "center", backgroundColor: colors.overlay, borderRadius: 10, padding: 8, marginTop: 6 },
  changedText: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.onSurfaceInverse, fontWeight: "600", flex: 1 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 10 },
  cardTitle: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface, marginBottom: 4 },
  note: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, fontStyle: "italic" },
  divider: { height: 1, backgroundColor: colors.divider },
  row: { flexDirection: "row", justifyContent: "space-between" },
  rowLabel: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary },
  rowValue: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurface, fontWeight: "600" },
  totalLabel: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  totalValue: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.brandPrimary },
  pay: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.brandSecondary, fontWeight: "700" },
  vatBox: { marginTop: 6, gap: 2 },
  vatTitle: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  vatLine: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  addr: { fontFamily: FONT_TEXT, fontSize: 15, color: colors.onSurface, lineHeight: 22 },
  notif: { flexDirection: "row", gap: 10, alignItems: "flex-start" },
  notifDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.brandPrimary, marginTop: 6 },
  notifTitle: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "700", color: colors.onSurface },
  notifBody: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, marginTop: 2 },
  notifTime: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
}));
