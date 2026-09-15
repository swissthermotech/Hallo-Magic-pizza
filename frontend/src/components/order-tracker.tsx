import React from "react";
import { Text, View } from "react-native";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { DELIVERY_FLOW, PICKUP_FLOW, statusLabel, useI18n } from "@/src/i18n";
import { fmtTime } from "@/src/format";
import { FONT_TEXT } from "./ui";
import type { Order } from "@/src/types";

const ICONS: Record<string, React.ComponentProps<typeof Feather>["name"]> = {
  pending: "inbox",
  accepted: "check-circle",
  preparing: "coffee",
  ready: "package",
  picked_up: "shopping-bag",
  assigned: "user-check",
  delivering: "truck",
  delivered: "home",
  completed: "flag",
};

export function OrderTracker({ order }: { order: Order }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const flow = (order.type === "pickup" ? PICKUP_FLOW : DELIVERY_FLOW).filter((s) => s !== "completed");
  const cancelled = order.status === "cancelled";
  const currentIdx = order.status === "completed" ? flow.length - 1 : flow.indexOf(order.status);
  const doneAt = (s: string) => order.status_history.find((h) => h.status === s)?.at;

  return (
    <View style={styles.wrap} testID="order-tracker">
      {flow.map((s, i) => {
        const done = !cancelled && i <= currentIdx;
        const active = !cancelled && i === currentIdx;
        const last = i === flow.length - 1;
        return (
          <View key={s} style={styles.row}>
            <View style={styles.rail}>
              <View style={[styles.dot, done && styles.dotDone, active && styles.dotActive, cancelled && i === 0 && styles.dotCancel]}>
                <Feather name={cancelled && i === 0 ? "x" : ICONS[s]} size={14} color={done || (cancelled && i === 0) ? colors.onBrandPrimary : colors.muted} />
              </View>
              {!last ? <View style={[styles.line, done && i < currentIdx && styles.lineDone]} /> : null}
            </View>
            <View style={[styles.content, last && { paddingBottom: 0 }]}>
              <Text style={[styles.label, done && styles.labelDone, active && styles.labelActive]} testID={`tracker-step-${s}`}>
                {statusLabel(s, order.type, t)}
              </Text>
              {doneAt(s) ? <Text style={styles.time}>{fmtTime(doneAt(s))}</Text> : null}
            </View>
          </View>
        );
      })}
      {cancelled ? (
        <View style={styles.cancelBox} testID="tracker-cancelled">
          <Feather name="x-circle" size={18} color={colors.error} />
          <Text style={styles.cancelText}>{t("orderCancelled")}{order.reject_reason ? ` – ${order.reject_reason}` : ""}</Text>
        </View>
      ) : null}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  wrap: { paddingVertical: 4 },
  row: { flexDirection: "row", gap: 14 },
  rail: { alignItems: "center", width: 30 },
  dot: { width: 30, height: 30, borderRadius: 15, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center", borderWidth: 2, borderColor: colors.border },
  dotDone: { backgroundColor: colors.brandSecondary, borderColor: colors.brandSecondary },
  dotActive: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary, shadowColor: colors.brandPrimary, shadowOpacity: 0.4, shadowRadius: 8, shadowOffset: { width: 0, height: 0 } },
  dotCancel: { backgroundColor: colors.error, borderColor: colors.error },
  line: { width: 2, flex: 1, minHeight: 22, backgroundColor: colors.border, marginVertical: 2 },
  lineDone: { backgroundColor: colors.brandSecondary },
  content: { flex: 1, paddingBottom: 18, paddingTop: 5, flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  label: { fontFamily: FONT_TEXT, fontSize: 15, color: colors.muted },
  labelDone: { color: colors.onSurface, fontWeight: "600" },
  labelActive: { color: colors.brandPrimary, fontWeight: "800" },
  time: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  cancelBox: { flexDirection: "row", gap: 8, alignItems: "center", backgroundColor: colors.brandSoft, borderRadius: 12, padding: 12, marginTop: 8 },
  cancelText: { fontFamily: FONT_TEXT, color: colors.error, fontWeight: "600", flex: 1 },
}));
