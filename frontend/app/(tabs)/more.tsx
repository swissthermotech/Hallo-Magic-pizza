import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu } from "@/src/api";
import { useAuth } from "@/src/auth";
import { FONT_DISPLAY, FONT_TEXT } from "@/src/components/ui";
import { LanguageToggle } from "./index";

const DAYS: Record<string, { fr: string; de: string }> = {
  mon: { fr: "Lundi", de: "Montag" }, tue: { fr: "Mardi", de: "Dienstag" }, wed: { fr: "Mercredi", de: "Mittwoch" },
  thu: { fr: "Jeudi", de: "Donnerstag" }, fri: { fr: "Vendredi", de: "Freitag" }, sat: { fr: "Samedi", de: "Samstag" }, sun: { fr: "Dimanche", de: "Sonntag" },
};

export default function MoreScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t, tx, lang } = useI18n();
  const { data } = useMenu();
  const s = data?.settings;
  const { user } = useAuth();

  const Row = ({ icon, label, onPress, testID, sub }: { icon: React.ComponentProps<typeof Feather>["name"]; label: string; onPress: () => void; testID: string; sub?: string }) => (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => [styles.row, pressed && { opacity: 0.8 }]}>
      <View style={styles.rowIcon}><Feather name={icon} size={18} color={colors.brandPrimary} /></View>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowLabel}>{label}</Text>
        {sub ? <Text style={styles.rowSub}>{sub}</Text> : null}
      </View>
      <Feather name="chevron-right" size={18} color={colors.muted} />
    </Pressable>
  );

  return (
    <View style={styles.screen}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Text style={styles.title} testID="more-title">{t("more")}</Text>
        <LanguageToggle />
      </View>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 24, gap: 20, width: "100%", maxWidth: 760, alignSelf: "center" }}>
        <View>
          <Text style={styles.section}>{t("account")}</Text>
          <View style={styles.card}>
            <Row icon="user" label={user ? `${user.first_name} ${user.last_name}`.trim() : t("account")} sub={user ? user.phone : t("accountHint")} onPress={() => router.push("/account")} testID="more-account" />
            <View style={styles.sep} />
            <Row icon="clock" label={t("myOrders")} onPress={() => router.push("/(tabs)/orders")} testID="more-my-orders" />
          </View>
        </View>
        <View>
          <Text style={styles.section}>{t("language")}</Text>
          <View style={styles.card}>
            {(["fr", "de"] as const).map((l, i) => (
              <LangRow key={l} l={l} last={i === 1} />
            ))}
          </View>
        </View>

        {s ? (
          <View>
            <Text style={styles.section}>{t("contact")} & {t("openingHours")}</Text>
            <View style={[styles.card, { padding: 16, gap: 6 }]}>
              <Text style={styles.brand}>{s.restaurant_name}</Text>
              <Text style={styles.info}>{s.address}</Text>
              <Text style={styles.info}>{s.phone}</Text>
              <View style={{ height: 8 }} />
              {Object.entries(s.opening_hours).map(([d, h]) => (
                <View key={d} style={styles.hoursRow}>
                  <Text style={styles.day}>{DAYS[d]?.[lang] ?? d}</Text>
                  <Text style={styles.hours}>{h || t("closedF")}</Text>
                </View>
              ))}
            </View>
          </View>
        ) : null}
        {s ? (
          <View testID="origin-section">
            <Text style={styles.section}>{t("meatFishOrigin")}</Text>
            <View style={[styles.card, { padding: 16 }]}>
              <Text style={styles.info}>{tx(s.meat_fish_origin) || t("notConfigured")}</Text>
            </View>
          </View>
        ) : null}

        <Pressable testID="more-staff-access" onPress={() => router.push("/staff/login")} style={styles.staffLink}>
          <Feather name="lock" size={13} color={colors.muted} />
          <Text style={styles.footer}>{t("staffAccess")}</Text>
        </Pressable>
        <Text style={styles.footer}>Hallo Magic Pizza · {tx({ fr: "Version test", de: "Testversion" })} · CHF</Text>
      </ScrollView>
    </View>
  );
}

function LangRow({ l, last }: { l: "fr" | "de"; last: boolean }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { lang, setLang, t } = useI18n();
  const on = lang === l;
  return (
    <>
      <Pressable testID={`lang-row-${l}`} onPress={() => setLang(l)} style={styles.row}>
        <Text style={styles.flag}>{l === "fr" ? "FR" : "DE"}</Text>
        <Text style={[styles.rowLabel, { flex: 1 }]}>{l === "fr" ? t("french") : t("german")}</Text>
        {on ? <Feather name="check-circle" size={20} color={colors.brandPrimary} /> : <View style={styles.circle} />}
      </Pressable>
      {!last ? <View style={styles.sep} /> : null}
    </>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: 16, paddingBottom: 12, flexDirection: "row", alignItems: "center", justifyContent: "space-between", borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.surface },
  title: { fontFamily: FONT_DISPLAY, fontSize: 28, color: colors.onSurface },
  section: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 8, marginLeft: 4 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, overflow: "hidden" },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, minHeight: 56 },
  rowIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: colors.brandSoft, alignItems: "center", justifyContent: "center" },
  rowLabel: { fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "600", color: colors.onSurface },
  rowSub: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, marginTop: 1 },
  sep: { height: 1, backgroundColor: colors.divider, marginLeft: 16 },
  flag: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "800", color: colors.onSurfaceInverse, backgroundColor: colors.surfaceInverse, width: 36, height: 36, borderRadius: 10, textAlign: "center", lineHeight: 36 },
  circle: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: colors.borderStrong },
  brand: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  info: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary },
  hoursRow: { flexDirection: "row", justifyContent: "space-between" },
  day: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.muted },
  hours: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurface, fontWeight: "600" },
  footer: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, textAlign: "center" },
  staffLink: { flexDirection: "row", gap: 6, alignItems: "center", justifyContent: "center", paddingVertical: 10, marginTop: 12 },
}));
