import React, { useState } from "react";
import { ActivityIndicator, Platform, Pressable, ScrollView, Share, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { fetchMarketingCsv, useCustomers } from "@/src/api";
import { useStaff } from "@/src/staff-auth";
import { chf, fmtDate } from "@/src/format";
import { Badge, Chip, Empty, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";
import type { CustomerSummary } from "@/src/types";

/** Staff customer database: accounts + guests in one list (one row per phone), search by name / phone / e-mail,
 * marketing-consent filter, CSV export of opted-in customers (manager). Tap a row -> full profile + order history. */
export default function StaffCustomersScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const toast = useToast();
  const { role } = useStaff();
  const [q, setQ] = useState("");
  const [marketing, setMarketing] = useState<"all" | "yes" | "no">("all");
  const { data, isFetching, isLoading } = useCustomers(q, marketing);
  const [exporting, setExporting] = useState(false);

  const exportCsv = async () => {
    setExporting(true);
    try {
      const csv = await fetchMarketingCsv();
      const name = `marketing-optin-${new Date().toISOString().slice(0, 10)}.csv`;
      if (Platform.OS === "web") {
        const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
        const a = document.createElement("a"); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url);
      } else {
        await Share.share({ message: csv, title: name });
      }
      toast.show(t("exportDone"), "success");
    } catch (e: any) {
      toast.show(e.message, "error");
    } finally {
      setExporting(false);
    }
  };

  return (
    <View style={styles.screen}>
      <ScreenHeader
        title={t("customers")}
        subtitle={data ? `${data.stats.total} ${t("customers").toLowerCase()} · ${data.stats.accounts} ${t("accounts").toLowerCase()} · ${data.stats.marketing_yes} ${t("marketingYes").toLowerCase()}` : undefined}
        testID="customers-title"
        right={role === "manager" ? (
          <Pressable testID="customers-export-csv" onPress={exportCsv} disabled={exporting} style={styles.iconBtn}>
            {exporting ? <ActivityIndicator color={colors.onSurface} /> : <Feather name="download" size={20} color={colors.onSurface} />}
          </Pressable>
        ) : undefined}
      />
      <View style={styles.searchWrap}>
        <Feather name="search" size={18} color={colors.muted} />
        <TextInput
          testID="customers-search-input"
          value={q}
          onChangeText={setQ}
          placeholder={t("searchCustomersPlaceholder")}
          placeholderTextColor={colors.muted}
          autoCorrect={false}
          style={styles.input}
        />
        {q ? <Pressable onPress={() => setQ("")} testID="customers-search-clear"><Feather name="x" size={18} color={colors.muted} /></Pressable> : null}
        {isFetching ? <ActivityIndicator color={colors.brandPrimary} /> : null}
      </View>
      <View style={styles.filters}>
        <Text style={styles.filterLabel}>{t("marketingConsentShort")}:</Text>
        {(["all", "yes", "no"] as const).map((m) => (
          <Chip key={m} label={m === "all" ? t("all") : m === "yes" ? t("yes") : t("no")} selected={marketing === m} onPress={() => setMarketing(m)} testID={`customers-filter-${m}`} />
        ))}
      </View>
      {isLoading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brandPrimary} /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, gap: 10, paddingBottom: insets.bottom + 24 }} keyboardShouldPersistTaps="handled">
          {data && data.customers.length === 0 ? <Empty icon="user-x" title={t("noResults")} /> : null}
          {data ? <Text style={styles.count} testID="customers-count">{data.count} {t("results").toLowerCase()}</Text> : null}
          {(data?.customers ?? []).map((c) => (
            <CustomerRow key={c.key} c={c} onPress={() => router.push({ pathname: "/staff/customers/[key]", params: { key: c.key } })} />
          ))}
        </ScrollView>
      )}
    </View>
  );
}

function CustomerRow({ c, onPress }: { c: CustomerSummary; onPress: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  return (
    <Pressable testID={`customer-row-${c.key}`} onPress={onPress} style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}>
      <View style={styles.rowBetween}>
        <Text style={styles.name} numberOfLines={1}>{c.first_name} {c.last_name}</Text>
        <View style={{ flexDirection: "row", gap: 6 }}>
          <Badge label={c.kind === "account" ? `★ ${t("accountBadge")}` : c.kind === "staff" ? t("phoneCustomer") : t("guest").toUpperCase()} tone={c.kind === "account" ? "brand" : "neutral"} />
          <Badge label={c.marketing.consent ? `✉ ${t("marketingYes")}` : `✉ ${t("marketingNo")}`} tone={c.marketing.consent ? "success" : "neutral"} testID={`customer-marketing-${c.key}`} />
        </View>
      </View>
      <Text style={styles.phone}>{c.phone}{c.email ? ` · ${c.email}` : ""}</Text>
      <View style={styles.stats}>
        <Stat icon="shopping-bag" label={`${c.orders_count} ${t("orders").toLowerCase()}`} />
        <Stat icon="calendar" label={`${t("lastOrder")}: ${fmtDate(c.last_order_at)}`} />
        <Stat icon="credit-card" label={chf(c.total_spent)} />
      </View>
      <Feather name="chevron-right" size={18} color={colors.muted} style={styles.chevron} />
    </Pressable>
  );
}

function Stat({ icon, label }: { icon: React.ComponentProps<typeof Feather>["name"]; label: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.stat}>
      <Feather name={icon} size={13} color={colors.muted} />
      <Text style={styles.statText}>{label}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  searchWrap: { flexDirection: "row", alignItems: "center", gap: 10, marginHorizontal: 16, marginTop: 12, height: 52, borderRadius: 14, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14 },
  input: { flex: 1, fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "600", color: colors.onSurface, height: 52 },
  filters: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16, paddingTop: 10, flexWrap: "wrap" },
  filterLabel: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  count: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 6, paddingRight: 34 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" },
  name: { fontFamily: FONT_TEXT, fontSize: 17, fontWeight: "800", color: colors.onSurface, flexShrink: 1 },
  phone: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary },
  stats: { flexDirection: "row", flexWrap: "wrap", gap: 12, marginTop: 2 },
  stat: { flexDirection: "row", alignItems: "center", gap: 5 },
  statText: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  chevron: { position: "absolute", right: 12, top: "50%" },
}));
