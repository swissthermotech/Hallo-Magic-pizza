import React, { useEffect, useMemo, useState } from "react";
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
import { useOrderingStatus } from "@/src/api";
import { useAuth } from "@/src/auth";
import { chf } from "@/src/format";
import { Button, Chip, Field, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";
import { OrderTypeSelector } from "./(tabs)/index";
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

  const type: OrderType = cart.orderType;
  const [timeMode, setTimeMode] = useState<"asap" | "scheduled">("asap");
  const [time, setTime] = useState<string>("");
  const [f, setF] = useState({ first_name: "", last_name: "", phone: "", email: "", street: "", number: "", npa: "", city: "", instructions: "" });
  const [ageOk, setAgeOk] = useState(false);
  const { data: ordering } = useOrderingStatus();
  // Scheduled ordering: a day (today + up to 7 days, closed days skipped) and only valid slots for that day
  const days = useMemo(() => ordering?.days ?? [], [ordering]);
  const [chosenDay, setChosenDay] = useState<string | null>(null);
  const hasSlots = (d: { pickup_slots: string[]; delivery_slots: string[] }) => (type === "delivery" ? d.delivery_slots : d.pickup_slots).length > 0;
  // Default day = first day that still has slots (ordering at 00:00 -> tomorrow); the customer can pick any listed day
  const dayIdx = Math.max(0, chosenDay ? days.findIndex((d) => d.date === chosenDay) : days.findIndex(hasSlots));
  const day = days[dayIdx] ?? days[0];
  const isFutureDay = !!day && !day.is_today;
  const pickDay = (i: number) => { setChosenDay(days[i].date); setTime(""); };
  // Only valid slots from the server schedule (opening hours, 15-min delivery cutoff, manager "first delivery")
  const slots = useMemo(() => {
    if (day) return type === "delivery" ? day.delivery_slots : day.pickup_slots;
    return ordering ? (type === "delivery" ? ordering.delivery_slots : ordering.pickup_slots) : timeSlots();
  }, [ordering, type, day]);
  const asapAvailable = !ordering || (type === "pickup" ? ordering.pickup_open : ordering.delivery_open);
  const closedNow = !!ordering && !ordering.pickup_open;
  useEffect(() => {
    if (!asapAvailable && timeMode === "asap") setTimeMode("scheduled");
  }, [asapAvailable, timeMode]);
  const dayLabel = (d: { date: string; weekday: string; is_today: boolean; is_tomorrow: boolean }) =>
    d.is_today ? t("today") : d.is_tomorrow ? t("tomorrow") : `${d.weekday} ${d.date.slice(8, 10)}.${d.date.slice(5, 7)}`;
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  // Optional account: prefill contact details + saved addresses (guest checkout unchanged)
  const { user } = useAuth();
  const [savedAddrId, setSavedAddrId] = useState<string | null>(null);
  const [saveAddress, setSaveAddress] = useState(true);
  useEffect(() => {
    if (!user) return;
    setF((p) => ({ ...p, first_name: p.first_name || user.first_name, last_name: p.last_name || user.last_name, phone: p.phone || user.phone, email: p.email || user.email || "" }));
    if (user.addresses.length && !savedAddrId) pickSavedAddress(user.addresses[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);
  const pickSavedAddress = (id: string | null) => {
    setSavedAddrId(id);
    const a = user?.addresses.find((x) => x.id === id);
    if (a) setF((p) => ({ ...p, street: a.street, number: a.number, npa: a.npa, city: a.city, instructions: a.instructions || "" }));
    else setF((p) => ({ ...p, street: "", number: "", npa: "", city: "", instructions: "" }));
  };

  const zone = settings?.delivery_zones.find((z) => z.npa === f.npa.trim());
  const zoneMissing = type === "delivery" && !!settings?.delivery_zones.length && f.npa.trim().length >= 4 && !zone;
  const minimum = zone?.minimum_order || settings?.minimum_order || 0;
  const goods = cart.subtotal + cart.extrasTotal;
  const fee = type === "delivery" && settings ? (settings.free_delivery_from && goods >= settings.free_delivery_from ? 0 : settings.delivery_fee) : 0;
  const total = goods + fee;
  const belowMin = type === "delivery" ? goods < minimum : false;
  const requestedTime = timeMode === "asap" ? "asap" : time;

  const valid =
    f.first_name.trim() && f.phone.trim() && (timeMode === "asap" ? asapAvailable : !!time && slots.includes(time)) && (type === "pickup" || (f.street.trim() && f.npa.trim() && f.city.trim() && !zoneMissing)) && (!cart.hasAlcohol || ageOk) && !belowMin && cart.items.length > 0;

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
        requested_date: timeMode === "scheduled" && isFutureDay ? day.date : null,
        general_note: cart.generalNote.trim() || undefined,
        age_confirmed: ageOk,
        save_address: !!user && type === "delivery" && !savedAddrId && saveAddress,
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
        <OrderTypeSelector />
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
          {closedNow ? (
            <View style={styles.closedBox} testID="checkout-closed">
              <Feather name="clock" size={16} color={colors.onError} />
              <Text style={styles.closedText}>{t("restaurantClosed")}{ordering?.next_open ? ` · ${t("nextOpening")}: ${ordering.next_open}` : ""}</Text>
            </View>
          ) : type === "delivery" && ordering && !ordering.delivery_open ? (
            <View style={[styles.closedBox, { backgroundColor: colors.warning }]} testID="checkout-delivery-unavailable">
              <Feather name="truck" size={16} color={colors.onWarning} />
              <Text style={[styles.closedText, { color: colors.onWarning }]}>{t("deliveryUnavailable")}</Text>
            </View>
          ) : type === "delivery" && ordering?.delivery_from ? (
            <Text style={styles.hint} testID="checkout-delivery-from">{t("earliestDelivery")}: {ordering.delivery_from}</Text>
          ) : null}
          <View style={[styles.segment, { marginBottom: 12 }]} testID="time-mode-segment">
            <Pressable testID="time-mode-asap" disabled={!asapAvailable} onPress={() => setTimeMode("asap")} style={[styles.segBtn, { height: 44 }, timeMode === "asap" && styles.segBtnActive, !asapAvailable && { opacity: 0.4 }]}>
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
              {days.length > 1 ? (
                <View style={[styles.slots, { marginBottom: 10 }]} testID="day-picker">
                  {days.map((d, i) => (
                    <Pressable key={d.date} testID={`day-${d.date}`} onPress={() => pickDay(i)} style={[styles.slot, dayIdx === i && styles.slotActive]}>
                      <Text style={[styles.slotText, dayIdx === i && styles.slotTextActive]}>{dayLabel(d)}</Text>
                    </Pressable>
                  ))}
                </View>
              ) : null}
              <View style={styles.slots}>
                {slots.length === 0 ? <Text style={styles.hint}>{t("restaurantClosed")}{ordering?.next_open ? ` – ${ordering.next_open}` : ""}</Text> : null}
                {slots.map((s) => (
                  <Pressable key={s} testID={`time-slot-${s.replace(":", "")}`} onPress={() => setTime(s)} style={[styles.slot, time === s && styles.slotActive]}>
                    <Text style={[styles.slotText, time === s && styles.slotTextActive]}>{s}</Text>
                  </Pressable>
                ))}
              </View>
              <Text style={[styles.hint, { marginTop: 10 }]} testID="scheduled-hint">{isFutureDay && day ? `${t("scheduledFor")} ${dayLabel(day)} (${day.date})${time ? ` · ${time}` : ""}. ` : ""}{t("notGuaranteed")}</Text>
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
          {type === "delivery" && user && user.addresses.length > 0 ? (
            <View style={{ gap: 8 }}>
              <Text style={styles.hint}>{t("useSavedAddress")}</Text>
              <View style={styles.wrap}>
                {user.addresses.map((a) => (
                  <Chip key={a.id} label={a.label || `${a.street} ${a.number}`.trim()} selected={savedAddrId === a.id} onPress={() => pickSavedAddress(a.id)} testID={`checkout-saved-address-${a.id}`} />
                ))}
                <Chip label={t("newAddress")} selected={!savedAddrId} onPress={() => pickSavedAddress(null)} testID="checkout-new-address" />
              </View>
            </View>
          ) : null}
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
              {user && !savedAddrId ? (
                <Pressable testID="checkout-save-address" onPress={() => setSaveAddress((v) => !v)} style={styles.checkRow}>
                  <View style={[styles.checkbox, styles.checkboxNeutral, saveAddress && styles.checkboxOn]}>{saveAddress ? <Feather name="check" size={16} color={colors.onBrandPrimary} /> : null}</View>
                  <Text style={styles.checkText}>{t("saveThisAddress")}</Text>
                </Pressable>
              ) : null}
            </>
          ) : null}
        </View>

        {cart.requiredAge ? (
          <Pressable testID="age-confirm-checkbox" onPress={() => setAgeOk((v) => !v)} style={styles.ageRow}>
            <View style={[styles.checkbox, ageOk && styles.checkboxOn]}>{ageOk ? <Feather name="check" size={16} color={colors.onBrandPrimary} /> : null}</View>
            <View style={{ flex: 1 }}>
              <Text style={styles.ageBadge} testID="age-required-label">{cart.requiredAge}+</Text>
              <Text style={styles.ageText}>{t(cart.requiredAge === 18 ? "ageConfirm18" : "ageConfirm16")}</Text>
            </View>
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
  closedBox: { flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: colors.error, borderRadius: 12, padding: 12, marginBottom: 12 },
  closedText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "800", color: colors.onError, flex: 1 },
  slot: { height: 40, paddingHorizontal: 14, borderRadius: 999, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, justifyContent: "center" },
  slotActive: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  slotText: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "600", color: colors.onSurface },
  slotTextActive: { color: colors.onBrandPrimary },
  two: { flexDirection: "row", gap: 10 },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  checkRow: { flexDirection: "row", gap: 12, alignItems: "center", paddingVertical: 4 },
  checkboxNeutral: { borderColor: colors.borderStrong },
  checkText: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurface, flex: 1 },
  ageBadge: { fontFamily: FONT_DISPLAY, fontSize: 18, color: colors.warning, marginBottom: 2 },
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
