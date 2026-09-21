import React from "react";
import { ActivityIndicator, Pressable, ScrollView, Switch, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { statusLabel, useI18n } from "@/src/i18n";
import { useCustomerProfile, useSetCustomerMarketing } from "@/src/api";
import { useStaff } from "@/src/staff-auth";
import { chf, fmtDate, fmtTime, statusTone } from "@/src/format";
import { sourceLabel } from "@/src/components/staff-order";
import { Badge, Empty, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";

/** Customer profile (staff): identity, contact, addresses, statistics, marketing consent, complete order history. */
export default function CustomerProfileScreen() {
  const { key } = useLocalSearchParams<{ key: string }>();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const toast = useToast();
  const { role } = useStaff();
  const { data: c, isLoading } = useCustomerProfile(key);
  const setMarketing = useSetCustomerMarketing();

  if (isLoading || !c) {
    return (
      <View style={styles.screen}>
        <ScreenHeader title={t("customerProfile")} testID="customer-profile-title" />
        {isLoading ? <View style={styles.center}><ActivityIndicator color={colors.brandPrimary} /></View> : <Empty icon="user-x" title={t("noResults")} />}
      </View>
    );
  }

  const kindLabel = c.kind === "account" ? `★ ${t("accountBadge")}` : c.kind === "staff" ? t("phoneCustomer") : t("guest").toUpperCase();
  const toggle = (v: boolean) =>
    setMarketing.mutateAsync({ key: c.key, consent: v }).then(() => toast.show(v ? t("marketingOn") : t("marketingOff"), "success")).catch((e) => toast.show(e.message, "error"));

  return (
    <View style={styles.screen}>
      <ScreenHeader title={`${c.first_name} ${c.last_name}`.trim() || t("customerProfile")} subtitle={kindLabel} testID="customer-profile-title" />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 16, paddingBottom: insets.bottom + 24 }}>
        {/* Identity & contact */}
        <View style={styles.card} testID="customer-profile-card">
          <Row label={t("firstName")} value={c.first_name || "—"} testID="customer-first-name" />
          <Row label={t("lastName")} value={c.last_name || "—"} testID="customer-last-name" />
          <Row label={t("phone")} value={c.phone || "—"} testID="customer-phone" />
          <Row label={t("email")} value={c.email || "—"} testID="customer-email" />
          <Row label={t("customerType")} value={kindLabel} testID="customer-kind" />
        </View>

        {/* Statistics */}
        <View style={styles.statsRow}>
          <StatBox label={t("orders")} value={String(c.orders_count)} testID="customer-orders-count" />
          <StatBox label={t("lastOrder")} value={fmtDate(c.last_order_at)} testID="customer-last-order" />
          <StatBox label={t("totalSpent")} value={chf(c.total_spent)} testID="customer-total-spent" />
        </View>

        {/* Addresses */}
        <View>
          <Text style={styles.section}>{t("deliveryAddresses")} ({c.addresses.length})</Text>
          <View style={styles.card}>
            {c.addresses.length === 0 ? <Text style={styles.hint}>{t("noAddresses")}</Text> : null}
            {c.addresses.map((a, i) => (
              <View key={i} style={styles.addr} testID={`customer-address-${i}`}>
                <Feather name="map-pin" size={14} color={colors.brandPrimary} />
                <Text style={styles.addrText}>{a}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Marketing consent */}
        <View>
          <Text style={styles.section}>{t("marketingTitle")}</Text>
          <View style={[styles.card, { gap: 10 }]} testID="customer-marketing-card">
            <View style={styles.rowBetween}>
              <Badge label={c.marketing.consent ? `✉ ${t("marketingYes")}` : `✉ ${t("marketingNo")}`} tone={c.marketing.consent ? "success" : "neutral"} testID="customer-marketing-status" />
              {role === "manager" ? (
                <Switch testID="customer-marketing-switch" value={c.marketing.consent} disabled={setMarketing.isPending} onValueChange={toggle} trackColor={{ true: colors.success, false: colors.borderStrong }} thumbColor={colors.surfaceSecondary} />
              ) : null}
            </View>
            {c.marketing.at ? <Text style={styles.hint} testID="customer-marketing-meta">{t("consentDate")}: {fmtDate(c.marketing.at)} {fmtTime(c.marketing.at)} · {t("consentSource")}: {t(`consentSource_${c.marketing.source || "unknown"}` as any) || c.marketing.source}</Text> : <Text style={styles.hint}>{t("noConsentRecorded")}</Text>}
            {role === "manager" ? <Text style={styles.hint}>{t("marketingStaffHint")}</Text> : null}
          </View>
        </View>

        {/* Order history */}
        <View>
          <Text style={styles.section}>{t("orderHistory")} ({c.orders.length})</Text>
          <View style={{ gap: 10 }}>
            {c.orders.length === 0 ? <View style={styles.card}><Text style={styles.hint}>{t("noHistory")}</Text></View> : null}
            {c.orders.map((o) => (
              <Pressable key={o.id} testID={`customer-order-${o.id}`} onPress={() => router.push({ pathname: "/staff/ticket/[id]", params: { id: o.id } })} style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}>
                <View style={styles.rowBetween}>
                  <Text style={styles.num}>#{o.order_number}</Text>
                  <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
                    <Badge label={o.type === "pickup" ? t("pickup").toUpperCase() : t("delivery").toUpperCase()} tone={o.type === "pickup" ? "neutral" : "brand"} />
                    <Badge label={sourceLabel(o.source, o.station)} tone={o.source === "telephone" ? "warning" : "inverse"} />
                    <Badge label={statusLabel(o.status, o.type, t)} tone={statusTone(o.status)} />
                  </View>
                </View>
                <Text style={styles.meta}>{fmtDate(o.created_at)} · {fmtTime(o.created_at)}{o.address ? ` · ${o.address.street} ${o.address.number}, ${o.address.npa} ${o.address.city}` : ""}</Text>
                <Text style={styles.items} numberOfLines={2}>{(o.items ?? []).map((i) => `${i.quantity}x ${i.name.fr}${i.size ? ` ${i.size.label}` : ""}`).join(", ")}</Text>
                <Text style={styles.total}>{chf(o.total)}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

function Row({ label, value, testID }: { label: string; value: string; testID: string }) {
  const styles = useStyles();
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue} testID={testID} selectable>{value}</Text>
    </View>
  );
}

function StatBox({ label, value, testID }: { label: string; value: string; testID: string }) {
  const styles = useStyles();
  return (
    <View style={styles.statBox}>
      <Text style={styles.statValue} testID={testID}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 6 },
  row: { flexDirection: "row", justifyContent: "space-between", gap: 12, paddingVertical: 4 },
  rowLabel: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  rowValue: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "700", color: colors.onSurface, flexShrink: 1, textAlign: "right" },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 },
  statsRow: { flexDirection: "row", gap: 10 },
  statBox: { flex: 1, backgroundColor: colors.surfaceInverse, borderRadius: 14, padding: 12, gap: 2 },
  statValue: { fontFamily: FONT_DISPLAY, fontSize: 18, color: colors.onSurfaceInverse },
  statLabel: { fontFamily: FONT_TEXT, fontSize: 11, color: colors.onSurfaceInverse, opacity: 0.8, textTransform: "uppercase", letterSpacing: 0.5 },
  section: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 8 },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  addr: { flexDirection: "row", gap: 6, alignItems: "center" },
  addrText: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary, flex: 1 },
  num: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
  meta: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.onSurfaceSecondary },
  items: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.onSurfaceSecondary },
  total: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.onSurface },
}));
