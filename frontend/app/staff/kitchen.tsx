import React from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, useWindowDimensions, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import { makeStyles, useTheme } from "@/src/theme";
import { statusLabel, useI18n } from "@/src/i18n";
import { useActiveOrders, useOrderAction } from "@/src/api";
import { elapsedMinutes, fmtTime } from "@/src/format";
import { Badge, Empty, FONT_DISPLAY, FONT_TEXT, useToast } from "@/src/components/ui";
import { OrderLines } from "@/src/components/order-lines";

export default function KitchenScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const toast = useToast();
  const { width } = useWindowDimensions();
  const cols = width >= 1100 ? 3 : width >= 700 ? 2 : 1;
  const { data, isLoading } = useActiveOrders(3000);
  const action = useOrderAction();
  const active = (data ?? []).filter((o) => ["accepted", "preparing"].includes(o.status)).sort((a, b) => (a.estimated_ready_at || "").localeCompare(b.estimated_ready_at || ""));

  const advance = async (id: string, status: string) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    try {
      await action.mutateAsync({ id, action: "status", body: { status } });
    } catch (e: any) {
      toast.show(e.message, "error");
    }
  };

  return (
    <View style={styles.screen}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Pressable testID="kitchen-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/staff"))} style={styles.iconBtn}><Feather name="arrow-left" size={20} color={colors.onSurfaceInverse} /></Pressable>
        <Text style={styles.title} testID="kitchen-title">{t("kitchen")}</Text>
        <Badge label={`${active.length}`} tone="brand" />
      </View>
      {isLoading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brandPrimary} size="large" /></View>
      ) : active.length === 0 ? (
        <View style={styles.center}><Empty icon="check-circle" title={t("kitchenEmpty")} /></View>
      ) : (
        <ScrollView contentContainerStyle={[styles.grid, { paddingBottom: insets.bottom + 24 }]}>
          {active.map((o) => {
            const late = o.estimated_ready_at && new Date(o.estimated_ready_at + "Z").getTime() < Date.now();
            return (
              <View key={o.id} style={[styles.card, { width: cols === 1 ? "100%" : cols === 2 ? "48.5%" : "32%" }, o.status === "preparing" && styles.cardPreparing]} testID={`kitchen-card-${o.id}`}>
                <View style={styles.cardHead}>
                  <Text style={styles.num}>#{o.order_number}</Text>
                  <View style={{ alignItems: "flex-end" }}>
                    <Text style={[styles.eta, late && { color: colors.error }]}>{fmtTime(o.estimated_ready_at)}</Text>
                    <Text style={styles.elapsed}>{elapsedMinutes(o.created_at)} min · {o.type === "pickup" ? t("pickup") : t("delivery")}</Text>
                  </View>
                </View>
                <OrderLines items={o.items} size="lg" showPrices={false} lang="fr" />
                {o.general_note ? <Text style={styles.note}>NOTE: {o.general_note.toUpperCase()}</Text> : null}
                <View style={styles.cardFoot}>
                  <Badge label={statusLabel(o.status, o.type, t)} tone={o.status === "preparing" ? "brand" : "warning"} />
                  {o.status === "accepted" ? (
                    <Pressable testID={`kitchen-start-${o.id}`} onPress={() => advance(o.id, "preparing")} style={[styles.bigBtn, { backgroundColor: colors.brandTertiary }]}>
                      <Feather name="play" size={18} color={colors.onBrandTertiary} />
                      <Text style={styles.bigBtnText}>{t("inPreparation")}</Text>
                    </Pressable>
                  ) : (
                    <Pressable testID={`kitchen-ready-${o.id}`} onPress={() => advance(o.id, "ready")} style={[styles.bigBtn, { backgroundColor: colors.success }]}>
                      <Feather name="check" size={18} color={colors.onSuccess} />
                      <Text style={styles.bigBtnText}>{t("readyBtn")}</Text>
                    </Pressable>
                  )}
                </View>
              </View>
            );
          })}
        </ScrollView>
      )}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surfaceInverse },
  header: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 12, paddingBottom: 10 },
  title: { flex: 1, fontFamily: FONT_DISPLAY, fontSize: 24, color: colors.onSurfaceInverse },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.overlay, alignItems: "center", justifyContent: "center" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 12, padding: 12, justifyContent: "flex-start" },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 16, gap: 12, borderLeftWidth: 6, borderLeftColor: colors.warning },
  cardPreparing: { borderLeftColor: colors.brandPrimary },
  cardHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  num: { fontFamily: FONT_DISPLAY, fontSize: 34, color: colors.onSurface },
  eta: { fontFamily: FONT_DISPLAY, fontSize: 28, color: colors.brandSecondary },
  elapsed: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  note: { fontFamily: FONT_TEXT, fontSize: 17, fontWeight: "800", color: colors.warning },
  cardFoot: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 10, marginTop: 4 },
  bigBtn: { flexDirection: "row", alignItems: "center", gap: 8, height: 56, paddingHorizontal: 18, borderRadius: 14 },
  bigBtnText: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.onBrandPrimary, letterSpacing: 0.5 },
}));
