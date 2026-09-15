import React, { useMemo, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView, KeyboardStickyView } from "react-native-keyboard-controller";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu, usePlaceOrder } from "@/src/api";
import { useCart } from "@/src/cart";
import { chf } from "@/src/format";
import { Button, Field, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";
import type { OrderType } from "@/src/types";

function timeSlots(): string[] {
  const out: string[] = [];
  const d = new Date();
  d.setMinutes(Math.ceil((d.getMinutes() + 30) / 15) * 15, 0, 0);
  for (let i = 0; i < 12; i++) {
    out.push(d.toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Zurich" }));
    d.setMinutes(d.getMinutes() + 15);
  }
  return out;
}

export default function CheckoutScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t, lang } = useI18n();
  const toast = useToast();
  const cart = useCart();
  const { data } = useMenu();
  const settings = data?.settings;
  const place = usePlaceOrder();

  const [type, setType] = useState<OrderType>(settings?.pickup_enabled === false ? "delivery" : "pickup");
  const [timeMode, setTimeMode] = useState<"asap" | "scheduled">("asap");
  const [time, setTime] = useState<string>("");
  const [f, setF] = useState({ first_name: "", last_name: "", phone: "", email: "", street: "", number: "", npa: "", city: "", instructions: "" });
  const [ageOk, setAgeOk] = useState(false);
  const slots = useMemo(timeSlots, []);
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  const zone = settings?.delivery_zones.find((z) => z.npa === f.npa.trim());
  const zoneMissing = type === "delivery" && !!settings?.delivery_zones.length && f.npa.trim().length >= 4 && !zone;
  const minimum = zone?.minimum_order || settings?.minimum_order || 0;
  const goods = cart.subtotal + cart.extrasTotal;
  const fee = type === "delivery" && settings ? (settings.free_delivery_from && goods >= settings.free_delivery_from ? 0 : settings.delivery_fee) : 0;
  const total = goods + fee;
  const belowMin = type === "delivery" ? goods < minimum : false;
  const requestedTime = timeMode === "asap" ? "asap" : time;

  const valid =
    f.first_name.trim() && f.phone.trim() && (timeMode === "asap" || !!time) && (type === "pickup" || (f.street.trim() && f.npa.trim() && f.city.trim() && !zoneMissing)) && (!cart.hasAlcohol || ageOk) && !belowMin && cart.items.length > 0;

  const submit = async () => {
    if (!valid) {
      toast.show(cart.hasAlcohol && !ageOk ? t("ageRequired") : t("required"), "error");
      return;
    }
    try {
      const order = await place.mutateAsync({
        type,
        items: cart.items,
        customer: { first_name: f.first_name.trim(), last_name: f.last_name.trim(), phone: f.phone.trim(), email: f.email.trim() || undefined },
        address: type === "delivery" ? { street: f.street.trim(), number: f.number.trim(), npa: f.npa.trim(), city: f.city.trim(), instructions: f.instructions.trim() || undefined } : undefined,
        requested_time: requestedTime,
        general_note: cart.generalNote.trim() || undefined,
        age_confirmed: ageOk,
        language: lang,
      });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      cart.addMyOrder(order.id);
      cart.clear();
      toast.show(t("orderPlaced"), "success");
      router.replace({ pathname: "/order/[id]", params: { id: order.id } });
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };

  const CTA_H = 110 + insets.bottom;

  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("checkout")} subtitle={`${cart.count} ${t("items").toLowerCase()} · ${chf(goods)}`} testID="checkout-title" />
      <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, paddingBottom: CTA_H + 16, gap: 20 }} bottomOffset={CTA_H + 16} showsVerticalScrollIndicator={false}>
        {/* Order type */}
        <View style={styles.segment} testID="order-type-segment">
          {(["pickup", "delivery"] as OrderType[]).map((tp) => {
            const enabled = tp === "pickup" ? settings?.pickup_enabled !== false : settings?.delivery_enabled !== false;
            return (
              <Pressable key={tp} testID={`order-type-${tp}`} disabled={!enabled} onPress={() => setType(tp)} style={[styles.segBtn, type === tp && styles.segBtnActive, !enabled && { opacity: 0.4 }]}>
                <Feather name={tp === "pickup" ? "shopping-bag" : "truck"} size={18} color={type === tp ? colors.onSurfaceInverse : colors.onSurface} />
                <Text style={[styles.segText, type === tp && styles.segTextActive]}>{t(tp).toUpperCase()}</Text>
              </Pressable>
            );
          })}
        </View>
        {type === "delivery" && settings ? (
          <Text style={[styles.hint, (belowMin || zoneMissing) && { color: colors.error }]} testID="delivery-min-hint">
            {zoneMissing
              ? t("zoneNotServed")
              : `${t("minOrder")}${zone ? ` (${zone.city})` : ""}: ${chf(minimum)}${settings.delivery_fee > 0 ? ` · ${t("deliveryFee")}: ${chf(settings.delivery_fee)}` : ""}`}
          </Text>
        ) : null}

        {/* Time */}
        <View>
          <Text style={styles.sectionTitle}>{t("desiredTime")}</Text>
          <View style={[styles.segment, { marginBottom: 12 }]} testID="time-mode-segment">
            <Pressable testID="time-mode-asap" onPress={() => setTimeMode("asap")} style={[styles.segBtn, { height: 44 }, timeMode === "asap" && styles.segBtnActive]}>
              <Feather name="zap" size={16} color={timeMode === "asap" ? colors.onSurfaceInverse : colors.onSurface} />
              <Text style={[styles.segText, { fontSize: 13 }, timeMode === "asap" && styles.segTextActive]}>{t("asap")}</Text>
            </Pressable>
            <Pressable testID="time-mode-scheduled" onPress={() => setTimeMode("scheduled")} style={[styles.segBtn, { height: 44 }, timeMode === "scheduled" && styles.segBtnActive]}>
              <Feather name="clock" size={16} color={timeMode === "scheduled" ? colors.onSurfaceInverse : colors.onSurface} />
              <Text style={[styles.segText, { fontSize: 13 }, timeMode === "scheduled" && styles.segTextActive]}>{t("chooseTime")}</Text>
            </Pressable>
          </View>
          {timeMode === "scheduled" ? (
            <>
              <View style={styles.slots}>
                {slots.map((s) => (
                  <Pressable key={s} testID={`time-slot-${s.replace(":", "")}`} onPress={() => setTime(s)} style={[styles.slot, time === s && styles.slotActive]}>
                    <Text style={[styles.slotText, time === s && styles.slotTextActive]}>{s}</Text>
                  </Pressable>
                ))}
              </View>
              <Text style={[styles.hint, { marginTop: 10 }]}>{t("notGuaranteed")}</Text>
            </>
          ) : null}
        </View>

        {/* Customer */}
        <View style={{ gap: 12 }}>
          <Text style={styles.sectionTitle}>{t("yourDetails")}</Text>
          <View style={styles.two}>
            <Field label={`${t("firstName")} *`} value={f.first_name} onChangeText={set("first_name")} style={{ flex: 1 }} testID="checkout-first-name" autoCapitalize="words" />
            <Field label={t("lastName")} value={f.last_name} onChangeText={set("last_name")} style={{ flex: 1 }} testID="checkout-last-name" autoCapitalize="words" />
          </View>
          <Field label={`${t("phone")} *`} value={f.phone} onChangeText={set("phone")} keyboardType="phone-pad" placeholder="079 123 45 67" testID="checkout-phone" />
          <Field label={t("email")} value={f.email} onChangeText={set("email")} keyboardType="email-address" autoCapitalize="none" testID="checkout-email" />
          {type === "delivery" ? (
            <>
              <View style={styles.two}>
                <Field label={`${t("street")} *`} value={f.street} onChangeText={set("street")} style={{ flex: 3 }} testID="checkout-street" />
                <Field label={t("number")} value={f.number} onChangeText={set("number")} style={{ flex: 1 }} testID="checkout-number" />
              </View>
              <View style={styles.two}>
                <Field label={`${t("npa")} *`} value={f.npa} onChangeText={set("npa")} keyboardType="number-pad" style={{ flex: 1 }} testID="checkout-npa" />
                <Field label={`${t("city")} *`} value={f.city} onChangeText={set("city")} style={{ flex: 2 }} testID="checkout-city" />
              </View>
              <Field label={t("deliveryInstructions")} value={f.instructions} onChangeText={set("instructions")} multiline testID="checkout-instructions" />
            </>
          ) : null}
        </View>

        {cart.hasAlcohol ? (
          <Pressable testID="age-confirm-checkbox" onPress={() => setAgeOk((v) => !v)} style={styles.ageRow}>
            <View style={[styles.checkbox, ageOk && styles.checkboxOn]}>{ageOk ? <Feather name="check" size={16} color={colors.onBrandPrimary} /> : null}</View>
            <Text style={styles.ageText}>{t("ageConfirm")}</Text>
          </Pressable>
        ) : null}

        {/* Payment */}
        <View style={styles.payBox}>
          <Feather name="credit-card" size={18} color={colors.brandSecondary} />
          <View style={{ flex: 1 }}>
            <Text style={styles.payTitle} testID="payment-method-label">{type === "pickup" ? t("payAtPickup") : t("payAtDelivery")}</Text>
            <Text style={styles.payHint}>{t("noOnlinePayment")}</Text>
          </View>
        </View>

        {/* Summary */}
        <View style={styles.summary}>
          <SumRow label={t("subtotal")} value={chf(cart.subtotal)} />
          <SumRow label={t("extrasTotal")} value={chf(cart.extrasTotal)} />
          {type === "delivery" ? <SumRow label={t("deliveryFee")} value={fee === 0 ? t("free") : chf(fee)} /> : null}
          <View style={styles.divider} />
          <View style={styles.row}>
            <Text style={styles.totalLabel}>{t("total")}</Text>
            <Text style={styles.totalValue} testID="checkout-total">{chf(total)}</Text>
          </View>
        </View>
      </KeyboardAwareScrollView>

      <KeyboardStickyView offset={{ closed: 0, opened: insets.bottom }}>
        <View style={[styles.cta, { paddingBottom: insets.bottom + 12 }]}>
          <Button title={`${t("confirmOrder")} · ${chf(total)}`} size="lg" icon="check" onPress={submit} loading={place.isPending} testID="confirm-order-button" />
          <Text style={styles.ctaHint}>{type === "pickup" ? t("payAtPickup") : t("payAtDelivery")}</Text>
        </View>
      </KeyboardStickyView>
    </View>
  );
}

function SumRow({ label, value }: { label: string; value: string }) {
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
  segment: { flexDirection: "row", backgroundColor: colors.surfaceTertiary, borderRadius: 14, padding: 4, gap: 4 },
  segBtn: { flex: 1, height: 52, borderRadius: 11, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  segBtnActive: { backgroundColor: colors.surfaceInverse },
  segText: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", letterSpacing: 0.5, color: colors.onSurface },
  segTextActive: { color: colors.onSurfaceInverse },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, marginTop: -10 },
  sectionTitle: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface, marginBottom: 10 },
  slots: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  slot: { height: 40, paddingHorizontal: 14, borderRadius: 999, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, justifyContent: "center" },
  slotActive: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  slotText: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "600", color: colors.onSurface },
  slotTextActive: { color: colors.onBrandPrimary },
  two: { flexDirection: "row", gap: 10 },
  ageRow: { flexDirection: "row", gap: 12, alignItems: "center", backgroundColor: colors.warningSoft, borderRadius: 12, padding: 14 },
  checkbox: { width: 26, height: 26, borderRadius: 7, borderWidth: 2, borderColor: colors.warning, alignItems: "center", justifyContent: "center" },
  checkboxOn: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  ageText: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurface, flex: 1, fontWeight: "600" },
  payBox: { flexDirection: "row", gap: 12, alignItems: "center", backgroundColor: colors.successSoft, borderRadius: 12, padding: 14 },
  payTitle: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.brandSecondary },
  payHint: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 2 },
  summary: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 8 },
  row: { flexDirection: "row", justifyContent: "space-between" },
  rowLabel: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary },
  rowValue: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurface, fontWeight: "600" },
  divider: { height: 1, backgroundColor: colors.divider, marginVertical: 4 },
  totalLabel: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  totalValue: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.brandPrimary },
  cta: { position: "absolute", left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 12, backgroundColor: colors.surfaceSecondary, borderTopWidth: 1, borderTopColor: colors.border, gap: 6 },
  ctaHint: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, textAlign: "center" },
}));
