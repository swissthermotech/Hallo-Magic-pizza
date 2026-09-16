import React from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { lineTotal, useCart } from "@/src/cart";
import { chf } from "@/src/format";
import { Button, Chip, Field, FONT_DISPLAY, FONT_TEXT, Stepper } from "@/src/components/ui";
import type { OrderAddress } from "./customer-panel";
import type { Settings, User } from "@/src/types";

export type PaymentMethod = "cash" | "terminal" | "pay_at_pickup" | "pay_at_delivery";

interface Props {
  settings?: Settings;
  customer: User | null;
  address: OrderAddress;
  timeMode: "asap" | "exact";
  onTimeMode: (m: "asap" | "exact") => void;
  time: string;
  onTime: (t: string) => void;
  payment: PaymentMethod;
  onPayment: (p: PaymentMethod) => void;
  onConfirm: () => void;
  busy: boolean;
  station: number;
}

/** Right pane: live cart + order options + recap + the single big confirmation button. */
export function OrderPanel(p: Props) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const cart = useCart();
  const delivery = cart.orderType === "delivery";
  const goods = cart.subtotal + cart.extrasTotal;
  const zone = p.settings?.delivery_zones.find((z) => z.npa === p.address.npa.trim());
  const minimum = zone?.minimum_order || p.settings?.minimum_order || 0;
  const fee = delivery && p.settings ? (p.settings.free_delivery_from && goods >= p.settings.free_delivery_from ? 0 : p.settings.delivery_fee) : 0;
  const total = goods + fee;
  const validTime = /^\d{1,2}:\d{2}$/.test(p.time.trim());
  const addrOk = !delivery || (p.address.street.trim() && p.address.npa.trim() && p.address.city.trim());
  // Staff may confirm below the usual web/app minimum – only a warning is shown
  const belowMinimum = delivery && minimum > 0 && goods < minimum;
  const canConfirm = !!p.customer && cart.items.length > 0 && addrOk && (p.timeMode === "asap" || validTime);
  const payments: { key: PaymentMethod; label: string; icon: React.ComponentProps<typeof Feather>["name"] }[] = [
    { key: "cash", label: t("payCash"), icon: "dollar-sign" },
    { key: "terminal", label: t("payTerminal"), icon: "credit-card" },
    delivery ? { key: "pay_at_delivery", label: t("payAtDelivery"), icon: "truck" } : { key: "pay_at_pickup", label: t("payAtPickup"), icon: "shopping-bag" },
  ];

  return (
    <View style={{ gap: 14 }}>
      {/* Type */}
      <View style={styles.segment}>
        {(["pickup", "delivery"] as const).map((k) => (
          <Pressable key={k} testID={`phone-type-${k}`} onPress={() => { cart.setOrderType(k); p.onPayment(k === "delivery" ? (p.payment === "pay_at_pickup" ? "pay_at_delivery" : p.payment) : p.payment === "pay_at_delivery" ? "pay_at_pickup" : p.payment); }} style={[styles.segBtn, cart.orderType === k && styles.segBtnOn]}>
            <Feather name={k === "pickup" ? "shopping-bag" : "truck"} size={18} color={cart.orderType === k ? colors.onSurfaceInverse : colors.onSurface} />
            <Text style={[styles.segText, cart.orderType === k && styles.segTextOn]}>{(k === "pickup" ? t("pickup") : t("delivery")).toUpperCase()}</Text>
          </Pressable>
        ))}
      </View>

      {/* Time */}
      <View style={styles.box}>
        <Text style={styles.kicker}>{t("desiredTime")}</Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <Chip label={t("asap")} selected={p.timeMode === "asap"} onPress={() => p.onTimeMode("asap")} testID="phone-time-asap" />
          <Chip label={t("exactTime")} selected={p.timeMode === "exact"} onPress={() => p.onTimeMode("exact")} testID="phone-time-exact" />
          {p.timeMode === "exact" ? (
            <TextInput testID="phone-time-input" value={p.time} onChangeText={p.onTime} placeholder="19:30" placeholderTextColor={colors.muted} keyboardType="numbers-and-punctuation" style={[styles.timeInput, p.time && !validTime && { borderColor: colors.error }]} />
          ) : null}
        </View>
        {p.timeMode === "exact" ? (
          <View style={styles.wrap}>
            {quickSlots().map((s) => <Chip key={s} label={s} selected={p.time === s} onPress={() => p.onTime(s)} testID={`phone-slot-${s.replace(":", "")}`} />)}
          </View>
        ) : null}
      </View>

      {/* Payment */}
      <View style={styles.box}>
        <Text style={styles.kicker}>{t("paymentMethod")}</Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          {payments.map((pm) => (
            <Pressable key={pm.key} testID={`phone-pay-${pm.key}`} onPress={() => p.onPayment(pm.key)} style={[styles.payBtn, p.payment === pm.key && styles.payBtnOn]}>
              <Feather name={pm.icon} size={16} color={p.payment === pm.key ? colors.onBrandPrimary : colors.onSurface} />
              <Text style={[styles.payText, p.payment === pm.key && { color: colors.onBrandPrimary }]} numberOfLines={2}>{pm.label}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      {/* Cart */}
      <View style={styles.box} testID="phone-cart">
        <View style={styles.rowBetween}>
          <Text style={styles.kicker}>{t("cart")} · {cart.count}</Text>
          {cart.items.length ? <Pressable testID="phone-cart-clear" onPress={cart.clear}><Text style={styles.linkText}>{t("delete").toUpperCase()}</Text></Pressable> : null}
        </View>
        {cart.items.length === 0 ? <Text style={styles.hint}>{t("emptyOrder")}</Text> : null}
        {cart.items.map((it) => (
          <View key={it.line_id} style={styles.line} testID={`phone-line-${it.line_id}`}>
            <View style={{ flex: 1 }}>
              <Text style={styles.lineName}>{it.name.fr}{it.size ? ` ${it.size.label}` : ""}</Text>
              {it.options.map((o) => <Text key={o.key} style={styles.mod}>* {o.name.fr}</Text>)}
              {it.removed_ingredients.map((r) => <Text key={r.id} style={[styles.mod, { color: colors.error }]}>– sans {r.fr}</Text>)}
              {it.extras.map((e) => <Text key={e.extra_id} style={[styles.mod, { color: colors.success }]}>+ {e.quantity > 1 ? `${e.quantity}x ` : ""}{e.name.fr}</Text>)}
              {it.note ? <Text style={[styles.mod, { color: colors.warning }]}>NOTE: {it.note}</Text> : null}
              <Text style={styles.linePrice}>{chf(lineTotal(it))}</Text>
            </View>
            <View style={{ alignItems: "flex-end", gap: 6 }}>
              <Stepper value={it.quantity} size={34} onChange={(v) => cart.updateItem(it.line_id, { quantity: v })} testID={`phone-qty-${it.line_id}`} />
              <View style={{ flexDirection: "row", gap: 6 }}>
                <Pressable testID={`phone-edit-${it.line_id}`} onPress={() => router.push({ pathname: "/product/[id]", params: { id: it.product_id, line: it.line_id } })} style={styles.iconBtn}><Feather name="edit-2" size={15} color={colors.onSurface} /></Pressable>
                <Pressable testID={`phone-remove-${it.line_id}`} onPress={() => cart.removeItem(it.line_id)} style={styles.iconBtn}><Feather name="trash-2" size={15} color={colors.error} /></Pressable>
              </View>
            </View>
          </View>
        ))}
        <Field label={t("orderNote")} value={cart.generalNote} onChangeText={cart.setGeneralNote} testID="phone-general-note" />
      </View>

      {/* Recap */}
      <View style={[styles.box, styles.recap]} testID="phone-recap">
        <Text style={[styles.kicker, { color: colors.onSurfaceInverse }]}>{t("summary")} · {t("phoneStation")} {p.station}</Text>
        <Text style={styles.recapLine} testID="phone-recap-customer">{p.customer ? `${p.customer.first_name} ${p.customer.last_name} · ${p.customer.phone}` : t("selectCustomerFirst")}</Text>
        {delivery ? <Text style={styles.recapLine}>{p.address.street} {p.address.number}, {p.address.npa} {p.address.city}{p.address.instructions ? ` · ${p.address.instructions}` : ""}</Text> : null}
        <Text style={styles.recapLine}>{delivery ? t("delivery") : t("pickup")} · {p.timeMode === "asap" ? t("asap") : p.time || "--:--"} · {payments.find((x) => x.key === p.payment)?.label}</Text>
        {cart.requiredAge ? <Text style={[styles.recapLine, { color: colors.warning, fontWeight: "800" }]}>⚠ {t("ageCheckRequired")}: {cart.requiredAge}+</Text> : null}
        {belowMinimum ? <Text style={[styles.recapLine, { color: colors.warning, fontWeight: "800" }]} testID="phone-below-minimum">⚠ {t("belowMinimum")} ({t("minOrder")}{zone ? ` ${zone.city}` : ""}: {chf(minimum)})</Text> : null}
        <View style={styles.divider} />
        <Row label={t("subtotal")} value={chf(cart.subtotal)} inverse />
        <Row label={t("extrasTotal")} value={chf(cart.extrasTotal)} inverse />
        {delivery ? <Row label={t("deliveryFee")} value={fee === 0 ? t("free") : chf(fee)} inverse /> : null}
        <View style={styles.rowBetween}>
          <Text style={styles.totalLabel}>{t("total")}</Text>
          <Text style={styles.totalValue} testID="phone-total">{chf(total)}</Text>
        </View>
      </View>

      <Button title={`${t("confirmPhoneOrder")} · ${chf(total)}`} size="xl" icon="phone-call" variant="success" disabled={!canConfirm} loading={p.busy} onPress={p.onConfirm} testID="phone-confirm" />
    </View>
  );
}

function Row({ label, value, inverse }: { label: string; value: string; inverse?: boolean }) {
  const styles = useStyles();
  return (
    <View style={styles.rowBetween}>
      <Text style={[styles.rowLabel, inverse && { color: styles.recapLine.color }]}>{label}</Text>
      <Text style={[styles.rowValue, inverse && { color: styles.recapLine.color }]}>{value}</Text>
    </View>
  );
}

function quickSlots(): string[] {
  const out: string[] = [];
  const d = new Date();
  d.setMinutes(Math.ceil((d.getMinutes() + 20) / 15) * 15, 0, 0);
  for (let i = 0; i < 8; i++) {
    out.push(d.toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Zurich" }));
    d.setMinutes(d.getMinutes() + 15);
  }
  return out;
}

const useStyles = makeStyles((colors) => ({
  segment: { flexDirection: "row", backgroundColor: colors.surfaceTertiary, borderRadius: 16, padding: 4, gap: 4 },
  segBtn: { flex: 1, height: 56, borderRadius: 13, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  segBtnOn: { backgroundColor: colors.surfaceInverse },
  segText: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", letterSpacing: 0.6, color: colors.onSurface },
  segTextOn: { color: colors.onSurfaceInverse },
  box: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10 },
  kicker: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "800", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8 },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  timeInput: { flex: 1, minWidth: 90, height: 40, borderRadius: 12, backgroundColor: colors.surface, borderWidth: 1.5, borderColor: colors.border, paddingHorizontal: 12, fontFamily: FONT_TEXT, fontSize: 18, fontWeight: "800", color: colors.onSurface, textAlign: "center" },
  payBtn: { flex: 1, minHeight: 56, borderRadius: 12, borderWidth: 1.5, borderColor: colors.border, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center", gap: 4, padding: 6 },
  payBtnOn: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  payText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "800", color: colors.onSurface, textAlign: "center" },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  linkText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "800", color: colors.brandPrimary },
  line: { flexDirection: "row", gap: 10, paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.divider },
  lineName: { fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "800", color: colors.onSurface },
  mod: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.onSurfaceSecondary, marginTop: 1 },
  linePrice: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "700", color: colors.onSurface, marginTop: 4 },
  iconBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  recap: { backgroundColor: colors.surfaceInverse, borderColor: colors.surfaceInverse },
  recapLine: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceInverse, lineHeight: 20 },
  divider: { height: 1, backgroundColor: colors.overlay, marginVertical: 4 },
  rowLabel: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary },
  rowValue: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "600", color: colors.onSurface },
  totalLabel: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurfaceInverse },
  totalValue: { fontFamily: FONT_DISPLAY, fontSize: 28, color: colors.onSurfaceInverse },
}));
