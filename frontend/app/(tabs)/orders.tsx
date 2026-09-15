import React from "react";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { statusLabel, useI18n } from "@/src/i18n";
import { useOrdersByIds } from "@/src/api";
import { useCart } from "@/src/cart";
import { chf, fmtTime, statusTone } from "@/src/format";
import { Badge, Button, Empty, FONT_DISPLAY, FONT_TEXT } from "@/src/components/ui";

export default function OrdersScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t, tx } = useI18n();
  const { myOrderIds } = useCart();
  const { data, refetch, isRefetching } = useOrdersByIds(myOrderIds);
  const orders = data ?? [];

  return (
    <View style={styles.screen}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Text style={styles.title} testID="orders-title">{t("myOrders")}</Text>
      </View>
      {myOrderIds.length === 0 ? (
        <Empty icon="clock" title={t("noOrders")} hint={t("noOrdersHint")} action={<Button title={t("browseMenu")} onPress={() => router.push("/(tabs)")} testID="orders-browse-menu-button" />} />
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 24, gap: 12 }} refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.brandPrimary} />}>
          {orders.map((o) => (
            <Pressable key={o.id} testID={`my-order-${o.id}`} onPress={() => router.push({ pathname: "/order/[id]", params: { id: o.id } })} style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}>
              <View style={styles.cardHead}>
                <Text style={styles.num}>#{o.order_number}</Text>
                <Badge label={statusLabel(o.status, o.type, t)} tone={statusTone(o.status)} />
              </View>
              <Text style={styles.meta}>
                {o.type === "pickup" ? t("pickup") : t("delivery")} · {fmtTime(o.created_at)} · {o.items.reduce((s, i) => s + i.quantity, 0)} {t("items").toLowerCase()}
              </Text>
              <Text style={styles.items} numberOfLines={2}>{o.items.map((i) => `${i.quantity}x ${tx(i.name)}`).join(", ")}</Text>
              <View style={styles.cardFoot}>
                {o.estimated_ready_at && o.status !== "cancelled" ? (
                  <View style={styles.eta}>
                    <Feather name="clock" size={14} color={colors.brandPrimary} />
                    <Text style={styles.etaText}>{o.type === "pickup" ? t("readyAround") : t("deliveryAround")} {fmtTime(o.estimated_ready_at)}</Text>
                  </View>
                ) : <View />}
                <Text style={styles.total}>{chf(o.total)}</Text>
              </View>
            </Pressable>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: 16, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.surface },
  title: { fontFamily: FONT_DISPLAY, fontSize: 28, color: colors.onSurface },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 6 },
  cardHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  num: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
  meta: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  items: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary, lineHeight: 20 },
  cardFoot: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 4 },
  eta: { flexDirection: "row", gap: 6, alignItems: "center" },
  etaText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.brandPrimary },
  total: { fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "800", color: colors.onSurface },
}));
