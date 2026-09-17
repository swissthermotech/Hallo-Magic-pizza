import React, { useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import { makeStyles, useTheme } from "@/src/theme";
import { statusLabel, useI18n } from "@/src/i18n";
import { useAssignDriver, useOrderAction, usePrintTicket } from "@/src/api";
import { chf, elapsedMinutes, fmtTime, statusTone } from "@/src/format";
import { Badge, Button, FONT_DISPLAY, FONT_TEXT, useToast } from "@/src/components/ui";
import { OrderLines } from "@/src/components/order-lines";
import type { Order } from "@/src/types";

const QUICK_MINUTES = [15, 20, 30, 40, 45, 60];

export function sourceLabel(src: string, station?: number | null) {
  if (src === "telephone") return `TÉLÉPHONE · POSTE ${station ?? 1}`;
  return src === "ios" ? "iPhone" : src === "android" ? "Android" : "Web";
}
const DRIVERS = ["Livreur 1", "Livreur 2", "Livreur 3"];

/** Compact order card for the queue list – one clearly separated block per order:
 *  1) number + status  2) source / type / age tags  3) times  4) customer  5) items  6) total + action hint */
export function OrderCard({ order: o, selected, onPress }: { order: Order; selected?: boolean; onPress: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const pending = o.status === "pending";
  const requested = o.requested_time && o.requested_time !== "asap" ? o.requested_time : null;
  return (
    <Pressable testID={`staff-order-card-${o.id}`} onPress={onPress} style={[styles.card, selected && styles.cardSelected, pending && styles.cardPending]}>
      <View style={styles.cardHead}>
        <Text style={styles.cardNum}>#{o.order_number}</Text>
        <Badge label={statusLabel(o.status, o.type, t)} tone={statusTone(o.status)} />
      </View>
      <View style={styles.tagRow}>
        <Badge label={sourceLabel(o.source, o.station)} tone={o.source === "telephone" ? "warning" : "inverse"} />
        <Badge label={o.type === "pickup" ? t("pickup").toUpperCase() : t("delivery").toUpperCase()} tone={o.type === "pickup" ? "success" : "brand"} />
        {o.age_required ? <Badge label={`${o.age_required}+`} tone="warning" testID={`staff-card-age-${o.id}`} /> : null}
        {o.driver ? <Badge label={`${o.driver}${o.driver_name ? ` — ${o.driver_name}` : ""}`} tone="neutral" /> : null}
      </View>
      <View style={styles.timeRow}>
        <View style={styles.timeCell}>
          <Text style={styles.timeCellLabel}>{t("mgrOrdered")}</Text>
          <Text style={styles.timeCellValue}>{fmtTime(o.created_at)} <Text style={styles.timeCellSub}>· {elapsedMinutes(o.created_at)} min</Text></Text>
        </View>
        <View style={styles.timeCell}>
          <Text style={styles.timeCellLabel}>{t("mgrRequested")}</Text>
          <Text style={[styles.timeCellValue, requested && { color: colors.brandTertiary }]}>{requested ?? t("asap")}</Text>
        </View>
        {o.estimated_ready_at ? (
          <View style={styles.timeCell}>
            <Text style={styles.timeCellLabel}>{t("mgrConfirmed")}</Text>
            <Text style={[styles.timeCellValue, { color: colors.brandSecondary }]}>{fmtTime(o.estimated_ready_at)}</Text>
          </View>
        ) : null}
      </View>
      <View style={styles.cardBody}>
        <Text style={styles.cardCustomer} numberOfLines={1}>{o.customer.first_name} {o.customer.last_name} · {o.customer.phone}</Text>
        {o.address ? <Text style={styles.cardAddress} numberOfLines={1}>{o.address.street} {o.address.number}, {o.address.npa} {o.address.city}</Text> : null}
        <Text style={styles.cardItems} numberOfLines={2}>{o.items.map((i) => `${i.quantity}x ${i.name.fr}${i.size ? ` ${i.size.label}` : ""}`).join(", ")}</Text>
      </View>
      <View style={styles.cardFoot}>
        <Text style={styles.cardTotal}>{chf(o.total)}</Text>
        <View style={[styles.cardCta, pending && styles.cardCtaPending]}>
          <Text style={[styles.cardCtaText, pending && { color: colors.onBrandPrimary }]}>{pending ? t("acceptAndConfirm") : t("mgrTapToProcess")}</Text>
          <Feather name="chevron-right" size={16} color={pending ? colors.onBrandPrimary : colors.onSurface} />
        </View>
      </View>
    </Pressable>
  );
}

/** Full order detail + very large action buttons */
export function OrderDetail({ order: o, onClose }: { order: Order; onClose?: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const action = useOrderAction();
  const print = usePrintTicket();
  const assign = useAssignDriver();
  const [customTime, setCustomTime] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);

  const run = async (act: "accept" | "reject" | "delay" | "status", body: object, haptic: "success" | "error" | "warning" = "success") => {
    try {
      await action.mutateAsync({ id: o.id, action: act, body });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType[haptic === "success" ? "Success" : haptic === "error" ? "Error" : "Warning"]).catch(() => {});
      if (act === "reject") onClose?.();
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };
  const validTime = /^\d{1,2}:\d{2}$/.test(customTime.trim());

  // 2-step acceptance: step 1 selects a time (nothing is sent), step 2 "ACCEPTER ET CONFIRMER" accepts.
  type Sel = { minutes?: number; time?: string };
  const [sel, setSel] = useState<Sel | null>(null);
  const pick = (s: Sel) => {
    Haptics.selectionAsync().catch(() => {});
    setSel(s);
  };
  const isSel = (s: Sel) => !!sel && sel.minutes === s.minutes && sel.time === s.time;
  const selTime = sel?.time
    ? sel.time
    : sel?.minutes !== undefined
      ? new Date(Date.now() + sel.minutes * 60000).toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Zurich" })
      : "";
  const openTicket = () => openStaffScreen("/staff/ticket/[id]");
  const openReceipt = () => openStaffScreen("/staff/receipt/[id]");
  const openStaffScreen = (pathname: "/staff/ticket/[id]" | "/staff/receipt/[id]") => {
    const go = () => router.push({ pathname, params: { id: o.id } });
    if (onClose) {
      // Detail is shown inside a Modal on phones: close it first, otherwise the ticket screen opens hidden behind it.
      onClose();
      setTimeout(go, 350);
    } else go();
  };
  const requested = o.requested_time && o.requested_time !== "asap" ? o.requested_time : null;
  const pending = o.status === "pending";
  const closed = o.status === "completed" || o.status === "cancelled";

  const nextSteps: { status: string; label: string; icon: React.ComponentProps<typeof Feather>["name"] }[] = [];
  if (!pending && !closed) {
    if (o.status === "accepted") nextSteps.push({ status: "preparing", label: t("inPreparation"), icon: "coffee" });
    if (["accepted", "preparing"].includes(o.status)) nextSteps.push({ status: "ready", label: t("readyBtn"), icon: "package" });
    if (o.type === "pickup") {
      if (o.status === "ready") nextSteps.push({ status: "picked_up", label: t("pickedUpBtn"), icon: "shopping-bag" });
    } else {
      if (["ready", "assigned"].includes(o.status)) nextSteps.push({ status: "delivering", label: t("outForDelivery"), icon: "truck" });
      if (o.status === "delivering") nextSteps.push({ status: "delivered", label: t("deliveredBtn"), icon: "home" });
    }
    if (["ready", "picked_up", "delivered", "delivering"].includes(o.status)) nextSteps.push({ status: "completed", label: t("completeBtn"), icon: "flag" });
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 16, gap: 16, paddingBottom: 40 }} testID="staff-order-detail">
      {/* Header: number + close, then one tag row (status / source / type / driver) */}
      <View style={styles.detailHead}>
        <View style={{ flex: 1 }}>
          <Text style={styles.detailNum} testID="staff-detail-number">#{o.order_number}</Text>
          <Text style={styles.detailMeta}>{t("mgrOrdered")} {fmtTime(o.created_at)} · {elapsedMinutes(o.created_at)} min</Text>
        </View>
        {onClose ? (
          <Pressable testID="staff-detail-close" onPress={onClose} style={styles.closeBtn}><Feather name="x" size={22} color={colors.onSurface} /></Pressable>
        ) : null}
      </View>
      <View style={styles.tagRow}>
        <Badge label={statusLabel(o.status, o.type, t)} tone={statusTone(o.status)} testID="staff-detail-status" />
        <Badge label={sourceLabel(o.source, o.station)} tone={o.source === "telephone" ? "warning" : "inverse"} />
        <Badge label={o.type === "pickup" ? t("pickup").toUpperCase() : t("delivery").toUpperCase()} tone={o.type === "pickup" ? "success" : "brand"} />
        {o.driver ? <Badge label={`${o.driver}${o.driver_name ? ` — ${o.driver_name}` : ""}`} tone="neutral" testID="staff-detail-driver" /> : null}
      </View>

      {/* Time block */}
      <View style={[styles.timeBox, pending && { backgroundColor: colors.warningSoft }]}>
        <View style={{ flex: 1 }}>
          <Text style={styles.timeLabel}>{o.type === "pickup" ? t("requestedPickup") : t("requestedDelivery")}</Text>
          <Text style={styles.timeValue} testID="staff-requested-time">{requested ?? t("asap")}</Text>
        </View>
        {o.estimated_ready_at ? (
          <View style={{ flex: 1, alignItems: "flex-end" }}>
            <Text style={styles.timeLabel}>{t("confirmedTime")}</Text>
            <Text style={[styles.timeValue, { color: colors.brandSecondary }]} testID="staff-confirmed-time">{fmtTime(o.estimated_ready_at)}</Text>
            {o.delay_minutes_total > 0 ? <Text style={styles.timeSub}>+{o.delay_minutes_total} min</Text> : null}
          </View>
        ) : null}
      </View>

      {/* Alcohol – age check at handover (pickup counter or delivery driver) */}
      {o.age_required ? (
        <View style={styles.ageBox} testID="staff-age-check">
          <Feather name="alert-triangle" size={26} color={colors.onWarning} />
          <View style={{ flex: 1 }}>
            <Text style={styles.ageTitle}>{t("ageCheckRequired")}: {o.age_required}+</Text>
            <Text style={styles.ageSub}>{t("ageCheckHint")}</Text>
          </View>
        </View>
      ) : null}

      {/* Customer */}
      <View style={styles.box}>
        <Text style={styles.sectionLabel}>{t("mgrCustomer")}</Text>
        <Text style={styles.boxTitle}>{o.customer.first_name} {o.customer.last_name}{o.user_id ? "  ·  ★" : ""}</Text>
        <Text style={styles.boxText}>{o.customer.phone}{o.customer.email ? ` · ${o.customer.email}` : ""}</Text>
        {o.address ? <Text style={styles.boxText}>{o.address.street} {o.address.number}, {o.address.npa} {o.address.city}{o.address.instructions ? `\n${o.address.instructions}` : ""}</Text> : null}
      </View>

      {/* Lines */}
      <View style={styles.box}>
        <Text style={styles.sectionLabel}>{t("mgrItems")} · {o.items.reduce((n, i) => n + i.quantity, 0)}</Text>
        <OrderLines items={o.items} size="lg" lang="fr" />
        {o.general_note ? <Text style={styles.generalNote}>NOTE: {o.general_note}</Text> : null}
        <View style={styles.totalRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.totalLabel}>{t("total")}{o.delivery_fee > 0 ? ` (${t("deliveryFee").toLowerCase()} ${chf(o.delivery_fee)})` : ""}</Text>
            <Text style={styles.pay}>{o.payment_method === "cash" ? t("payCash").toUpperCase() : o.payment_method === "terminal" ? t("payTerminal").toUpperCase() : o.payment_method === "pay_at_pickup" ? t("payAtPickup").toUpperCase() : t("payAtDelivery").toUpperCase()}</Text>
          </View>
          <Text style={styles.totalValue} testID="staff-detail-total">{chf(o.total)}</Text>
        </View>
      </View>

      {/* Actions */}
      {pending ? (
        <View style={[styles.box, styles.actionBox]}>
          <Text style={styles.sectionLabel}>{t("mgrAcceptOrder")}</Text>
          <Text style={styles.actionLabel}>1 · {requested ? `${t("confirm")} ${requested} / ${t("changeTo")}` : t("estimatedPrep")}</Text>
          {requested ? (
            <Pressable testID="staff-confirm-requested-time" onPress={() => pick({ time: requested })} style={[styles.minuteBtn, { width: "100%", flexDirection: "row", gap: 10 }, isSel({ time: requested }) && styles.minuteBtnSel]}>
              <Feather name="check-circle" size={22} color={colors.onSurfaceInverse} />
              <Text style={styles.minuteText}>{t("confirm")} {requested}</Text>
            </Pressable>
          ) : null}
          <View style={styles.minuteGrid}>
            {QUICK_MINUTES.map((m) => (
              <Pressable key={m} testID={`staff-accept-${m}`} onPress={() => pick({ minutes: m })} style={[styles.minuteBtn, isSel({ minutes: m }) && styles.minuteBtnSel]}>
                <Text style={styles.minuteText}>{m}</Text>
                <Text style={styles.minuteUnit}>min</Text>
              </Pressable>
            ))}
          </View>
          <View style={styles.customRow}>
            <TextInput testID="staff-custom-time-input" value={customTime} onChangeText={setCustomTime} placeholder="19:45" placeholderTextColor={colors.muted} style={styles.customInput} keyboardType="numbers-and-punctuation" />
            <Button title={t("customTime")} variant={isSel({ time: customTime.trim() }) && validTime ? "primary" : "secondary"} disabled={!validTime} onPress={() => pick({ time: customTime.trim() })} style={{ flex: 1 }} testID="staff-accept-custom-time" />
          </View>

          <Text style={styles.actionLabel}>2 · {t("confirm")}</Text>
          <Button
            title={sel ? `${t("acceptAndConfirm")} · ${selTime}` : t("acceptAndConfirm")}
            size="xl"
            icon="check-circle"
            variant="success"
            disabled={!sel}
            loading={action.isPending}
            onPress={() => sel && run("accept", sel)}
            testID="staff-accept-confirm"
          />
          {!showReject ? (
            <Button title={t("reject")} size="lg" icon="x-circle" variant="danger" onPress={() => setShowReject(true)} testID="staff-reject-button" />
          ) : (
            <View style={{ gap: 10 }}>
              <TextInput testID="staff-reject-reason" value={rejectReason} onChangeText={setRejectReason} placeholder={t("rejectReason")} placeholderTextColor={colors.muted} style={[styles.customInput, { width: "100%", textAlign: "left" }]} />
              <View style={{ flexDirection: "row", gap: 10 }}>
                <Button title={t("close")} variant="outline" onPress={() => setShowReject(false)} style={{ flex: 1 }} testID="staff-reject-cancel" />
                <Button title={t("reject")} variant="danger" size="lg" loading={action.isPending} onPress={() => run("reject", { reason: rejectReason.trim() || undefined }, "error")} style={{ flex: 2 }} testID="staff-reject-confirm" />
              </View>
            </View>
          )}
        </View>
      ) : !closed ? (
        <View style={{ gap: 12 }}>
          {/* 1. Next step – the primary action */}
          {nextSteps.length ? (
            <View style={[styles.box, styles.actionBox]}>
              <Text style={styles.sectionLabel}>{t("mgrNextStep")}</Text>
              {nextSteps.map((s) => (
                <Button key={s.status} title={s.label} size="xl" icon={s.icon} variant={s.status === "completed" ? "primary" : "success"} loading={action.isPending} onPress={() => run("status", { status: s.status })} testID={`staff-status-${s.status}`} />
              ))}
            </View>
          ) : null}
          {/* 2. Driver assignment (delivery only) */}
          {o.type === "delivery" ? (
            <View style={styles.box}>
              <Text style={styles.sectionLabel}>{t("mgrDriver")}{o.driver ? ` · ${o.driver}${o.driver_name ? ` — ${o.driver_name}` : ""}` : ""}</Text>
              <View style={{ flexDirection: "row", gap: 8 }}>
                {DRIVERS.map((d) => (
                  <Button key={d} title={d} variant={o.driver === d ? "success" : "outline"} onPress={() => assign.mutateAsync({ id: o.id, driver: d }).catch((e) => toast.show(e.message, "error"))} style={{ flex: 1 }} testID={`staff-assign-${d.slice(-1)}`} />
                ))}
              </View>
            </View>
          ) : null}
          {/* 3. Delay (customer is notified) */}
          <View style={styles.box}>
            <Text style={styles.sectionLabel}>{t("mgrDelay")}{o.estimated_ready_at ? ` · ${t("confirmedTime").toLowerCase()} ${fmtTime(o.estimated_ready_at)}` : ""}</Text>
            <View style={{ flexDirection: "row", gap: 10 }}>
              {[5, 10, 15].map((m) => (
                <Pressable key={m} testID={`staff-delay-${m}`} disabled={action.isPending} onPress={() => run("delay", { minutes: m }, "warning")} style={[styles.minuteBtn, styles.delayBtn, { flex: 1, height: 56 }]}>
                  <Text style={[styles.minuteText, { color: colors.onWarning, fontSize: 22 }]}>+{m}</Text>
                  <Text style={[styles.minuteUnit, { color: colors.onWarning }]}>min</Text>
                </Pressable>
              ))}
            </View>
            <View style={styles.customRow}>
              <TextInput testID="staff-delay-time-input" value={customTime} onChangeText={setCustomTime} placeholder="20:15" placeholderTextColor={colors.muted} style={styles.customInput} keyboardType="numbers-and-punctuation" />
              <Button title={t("customTime")} variant="secondary" disabled={!validTime} onPress={() => run("delay", { time: customTime.trim() }, "warning")} style={{ flex: 1 }} testID="staff-delay-custom-time" />
            </View>
          </View>
          {/* 4. Cancel – kept apart from the positive actions */}
          <Button title={t("mgrCancelOrder")} variant="outline" icon="x-circle" onPress={() => run("reject", {}, "error")} testID="staff-cancel-order" />
        </View>
      ) : null}

      {/* Ticket */}
      <View style={styles.box}>
        <Text style={styles.sectionLabel}>{t("mgrTicket")}</Text>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
          <Feather name="printer" size={18} color={o.printed ? colors.success : colors.muted} />
          <Text style={[styles.boxText, { flex: 1 }]} testID="staff-print-status">
            {o.print_status === "failed" ? `⚠ ${t("printFailed")} · ${o.print_attempts}x` : o.printed ? `${t("printed")} ${fmtTime(o.printed_at)} · ${o.print_attempts}x${o.print_status ? ` · ${o.print_status}` : ""}` : t("notPrinted")}
          </Text>
        </View>
        <View style={{ gap: 10, marginTop: 6 }}>
          <Button
            title={o.print_status === "failed" ? t("retryPrint") : o.printed ? t("reprintTicket") : t("printTicket")}
            variant="secondary"
            icon="printer"
            loading={print.isPending}
            onPress={() => print.mutateAsync({ id: o.id, force: o.printed }).then(() => toast.show(t("printed"), "success")).catch((e) => toast.show(e.message, "error"))}
            testID="staff-print-button"
          />
          <View style={{ flexDirection: "row", gap: 10 }}>
            <Button title={t("ticketPreview")} variant="outline" icon="file-text" onPress={openTicket} style={{ flex: 1 }} testID="staff-ticket-preview" />
            <Button title={`${t("receiptPreview")}${o.receipt_printed ? ` · ${o.receipt_print_attempts}x` : ""}`} variant="outline" icon="file" onPress={openReceipt} style={{ flex: 1 }} testID="staff-receipt-preview" />
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

const useStyles = makeStyles((colors) => ({
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1.5, borderColor: colors.border, padding: 14, gap: 10 },
  cardSelected: { borderColor: colors.surfaceInverse },
  cardPending: { borderColor: colors.brandPrimary, backgroundColor: colors.brandSoft },
  cardHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 },
  cardNum: { fontFamily: FONT_DISPLAY, fontSize: 26, color: colors.onSurface },
  tagRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, alignItems: "center" },
  timeRow: { flexDirection: "row", gap: 8, backgroundColor: colors.surfaceTertiary, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8 },
  timeCell: { flex: 1, minWidth: 0 },
  timeCellLabel: { fontFamily: FONT_TEXT, fontSize: 10, fontWeight: "800", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  timeCellValue: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.onSurface, marginTop: 1 },
  timeCellSub: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "600", color: colors.muted },
  cardBody: { gap: 2 },
  cardCustomer: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "700", color: colors.onSurface },
  cardAddress: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  cardItems: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.onSurfaceSecondary, lineHeight: 18, marginTop: 2 },
  cardFoot: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", borderTopWidth: 1, borderTopColor: colors.divider, paddingTop: 10 },
  cardTotal: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  cardCta: { flexDirection: "row", alignItems: "center", gap: 4, height: 36, paddingLeft: 12, paddingRight: 6, borderRadius: 18, backgroundColor: colors.surfaceTertiary },
  cardCtaPending: { backgroundColor: colors.brandPrimary },
  cardCtaText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "800", color: colors.onSurface, textTransform: "uppercase", letterSpacing: 0.4 },
  detailHead: { flexDirection: "row", alignItems: "center", gap: 12 },
  detailNum: { fontFamily: FONT_DISPLAY, fontSize: 34, color: colors.onSurface },
  detailMeta: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  closeBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  timeBox: { flexDirection: "row", backgroundColor: colors.surfaceTertiary, borderRadius: 14, padding: 14 },
  timeLabel: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  timeValue: { fontFamily: FONT_DISPLAY, fontSize: 30, color: colors.onSurface, marginTop: 2 },
  timeSub: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.warning, fontWeight: "700" },
  ageBox: { flexDirection: "row", alignItems: "center", gap: 14, backgroundColor: colors.warning, borderRadius: 14, padding: 14 },
  ageTitle: { fontFamily: FONT_TEXT, fontSize: 17, fontWeight: "900", color: colors.onWarning, letterSpacing: 0.4 },
  ageSub: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "600", color: colors.onWarning, opacity: 0.9, marginTop: 2 },
  box: { backgroundColor: colors.surfaceSecondary, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 8 },
  actionBox: { borderColor: colors.borderStrong, borderWidth: 1.5 },
  sectionLabel: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "800", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 2 },
  boxTitle: { fontFamily: FONT_TEXT, fontSize: 18, fontWeight: "800", color: colors.onSurface },
  boxText: { fontFamily: FONT_TEXT, fontSize: 15, color: colors.onSurfaceSecondary, lineHeight: 21 },
  generalNote: { fontFamily: FONT_TEXT, fontSize: 16, color: colors.warning, fontWeight: "800", marginTop: 10 },
  totalRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12, marginTop: 12, borderTopWidth: 1, borderTopColor: colors.divider, paddingTop: 10 },
  totalLabel: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.muted },
  totalValue: { fontFamily: FONT_DISPLAY, fontSize: 26, color: colors.onSurface },
  pay: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "800", color: colors.brandSecondary, letterSpacing: 0.5, marginTop: 2 },
  actionLabel: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  minuteGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  minuteBtn: { width: "30%", flexGrow: 1, height: 64, borderRadius: 14, backgroundColor: colors.surfaceInverse, alignItems: "center", justifyContent: "center", borderWidth: 3, borderColor: colors.surfaceInverse },
  minuteBtnSel: { backgroundColor: colors.success, borderColor: colors.brandSecondary },
  delayBtn: { backgroundColor: colors.warning },
  minuteText: { fontFamily: FONT_DISPLAY, fontSize: 26, color: colors.onSurfaceInverse },
  minuteUnit: { fontFamily: FONT_TEXT, fontSize: 11, color: colors.onSurfaceInverse, opacity: 0.8 },
  customRow: { flexDirection: "row", gap: 10, alignItems: "center" },
  customInput: { height: 48, width: 110, borderRadius: 12, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14, fontFamily: FONT_TEXT, fontSize: 18, fontWeight: "700", color: colors.onSurface, textAlign: "center" },
}));
