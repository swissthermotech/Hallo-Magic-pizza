import React, { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useClosing, useSaveClosing, useSources, type DriverClosing } from "@/src/api";
import { chf, fmtTime } from "@/src/format";
import { Badge, Button, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";

const today = () => new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Zurich" }); // YYYY-MM-DD
const shift = (d: string, days: number) => {
  const x = new Date(d + "T12:00:00");
  x.setDate(x.getDate() + days);
  return x.toISOString().slice(0, 10);
};

/** Manager: end-of-day closing – one card per real driver identity (slot + person) + daily totals per order source. */
export default function ClosingScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const [date, setDate] = useState(today());
  const { data, isLoading } = useClosing(date);
  const { data: src } = useSources(date);

  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("closing")} subtitle={t("closingHint")} testID="closing-title" right={
        <View style={styles.dateRow}>
          <Pressable testID="closing-prev-day" onPress={() => setDate(shift(date, -1))} style={styles.dateBtn}><Feather name="chevron-left" size={18} color={colors.onSurface} /></Pressable>
          <Text style={styles.date} testID="closing-date">{date}</Text>
          <Pressable testID="closing-next-day" onPress={() => setDate(shift(date, 1))} style={styles.dateBtn}><Feather name="chevron-right" size={18} color={colors.onSurface} /></Pressable>
        </View>
      } />
      {isLoading || !data ? <View style={styles.center}><ActivityIndicator color={colors.brandPrimary} /></View> : (
        <ScrollView contentContainerStyle={{ padding: 16, gap: 16, paddingBottom: insets.bottom + 30 }}>
          {data.drivers.map((d) => <DriverBlock key={d.identity_key} d={d} />)}
          {src ? (
            <View style={styles.card} testID="sources-report">
              <Text style={styles.cardTitle}>{t("bySource")}</Text>
              {src.sources.map((s) => (
                <View key={s.source} style={styles.row}><Text style={styles.label}>{s.source}</Text><Text style={styles.value}>{s.count} · {chf(s.total)}</Text></View>
              ))}
              <View style={styles.divider} />
              <View style={styles.row}><Text style={styles.total}>{t("total")}</Text><Text style={styles.total}>{src.total_count} · {chf(src.total)}</Text></View>
            </View>
          ) : null}
        </ScrollView>
      )}
    </View>
  );
}

function DriverBlock({ d }: { d: DriverClosing }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const save = useSaveClosing();
  const [cash, setCash] = useState(d.actual_cash != null ? String(d.actual_cash) : "");
  const [term, setTerm] = useState(d.actual_terminal != null ? String(d.actual_terminal) : "");
  const [open, setOpen] = useState(false);
  const num = (v: string) => (v.trim() === "" ? null : parseFloat(v.replace(",", ".")));
  const diff = (actual: string, expected: number) => (num(actual) == null || isNaN(num(actual)!) ? null : Math.round((num(actual)! - expected) * 100) / 100);
  const Diff = ({ v }: { v: number | null }) => v == null ? <Text style={styles.value}>–</Text> : <Text style={[styles.value, { color: v === 0 ? colors.success : colors.error, fontWeight: "900" }]}>{v > 0 ? "+" : ""}{chf(v)}</Text>;

  const k = d.identity_key;

  return (
    <View style={[styles.card, d.is_current && styles.cardCurrent]} testID={`closing-${k}`}>
      <View style={styles.row}>
        <View style={{ flex: 1 }}>
          <Text style={styles.cardKicker}>{d.driver.toUpperCase()}{d.is_current ? ` · ${t("mgrOnDuty").toUpperCase()}` : ""}</Text>
          <Text style={styles.cardTitle} testID={`closing-name-${k}`}>{d.driver_name ?? d.label.split(" — ")[1]}</Text>
          {d.legacy ? <Text style={styles.small}>{t("mgrLegacyHint")}</Text> : null}
        </View>
        <Badge label={`${d.deliveries} ${t("deliveries")}${d.cancelled ? ` · ${d.cancelled} ${t("status_cancelled").toLowerCase()}` : ""}`} tone="brand" />
      </View>
      <View style={styles.row}><Text style={styles.label}>{t("payCash")}</Text><Text style={styles.value} testID={`closing-cash-${k}`}>{chf(d.cash_expected)}</Text></View>
      <View style={styles.row}><Text style={styles.label}>{t("payTerminal")}</Text><Text style={styles.value}>{chf(d.terminal_expected)}</Text></View>
      <View style={styles.row}><Text style={styles.label}>{t("alreadyPaid")}</Text><Text style={styles.value}>{chf(d.paid_no_collection)}</Text></View>
      <View style={styles.divider} />
      <View style={styles.row}><Text style={styles.total}>{t("total")}</Text><Text style={styles.total} testID={`closing-total-${k}`}>{chf(d.total)}</Text></View>

      <View style={styles.inputs}>
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={styles.small}>{t("actualCash")}</Text>
          <TextInput testID={`closing-actual-cash-${k}`} value={cash} onChangeText={setCash} keyboardType="decimal-pad" placeholder="0.00" placeholderTextColor={colors.muted} style={styles.input} />
          <View style={styles.row}><Text style={styles.small}>{t("difference")}</Text><Diff v={diff(cash, d.cash_expected)} /></View>
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={styles.small}>{t("actualTerminal")}</Text>
          <TextInput testID={`closing-actual-terminal-${k}`} value={term} onChangeText={setTerm} keyboardType="decimal-pad" placeholder="0.00" placeholderTextColor={colors.muted} style={styles.input} />
          <View style={styles.row}><Text style={styles.small}>{t("difference")}</Text><Diff v={diff(term, d.terminal_expected)} /></View>
        </View>
      </View>
      <Button title={t("saveClosing")} icon="save" variant="secondary" loading={save.isPending} onPress={() => save.mutateAsync({ date: d.date, driver: d.driver, driver_name: d.driver_name ?? null, actual_cash: num(cash), actual_terminal: num(term) }).then(() => toast.show(t("saved"), "success")).catch((e) => toast.show(e.message, "error"))} testID={`closing-save-${k}`} />
      {d.closed_at ? <Text style={styles.small}>✓ {t("saved")} {fmtTime(d.closed_at)}</Text> : null}

      {d.orders.length ? (
        <Pressable testID={`closing-toggle-${k}`} onPress={() => setOpen((v) => !v)} style={styles.row}><Text style={styles.link}>{open ? "−" : "+"} {d.orders.length} {t("orders").toLowerCase()}</Text></Pressable>
      ) : null}
      {open ? d.orders.map((o) => (
        <View key={o.id} style={styles.row}>
          <Text style={styles.small}>#{o.order_number} · {o.city} · {o.status === "cancelled" ? t("status_cancelled") : fmtTime(o.delivered_at)} · {o.collection_method.toUpperCase()}{o.payment_collected ? " ✓" : ""}</Text>
          <Text style={[styles.small, o.status === "cancelled" && { textDecorationLine: "line-through" }]}>{chf(o.total)}</Text>
        </View>
      )) : null}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  dateRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  dateBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  date: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "800", color: colors.onSurface },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 8 },
  cardCurrent: { borderColor: colors.success, borderWidth: 1.5 },
  cardKicker: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "800", color: colors.muted, letterSpacing: 0.8 },
  cardTitle: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  label: { fontFamily: FONT_TEXT, fontSize: 15, color: colors.onSurfaceSecondary },
  value: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "700", color: colors.onSurface },
  total: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  divider: { height: 1, backgroundColor: colors.divider },
  inputs: { flexDirection: "row", gap: 12, marginTop: 6 },
  small: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  input: { height: 46, borderRadius: 12, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, fontFamily: FONT_TEXT, fontSize: 17, fontWeight: "700", color: colors.onSurface },
  link: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "800", color: colors.brandPrimary },
}));
