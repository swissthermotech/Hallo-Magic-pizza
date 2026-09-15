import React from "react";
import { Pressable, Text, View } from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu } from "@/src/api";
import { lineTotal, useCart } from "@/src/cart";
import { chf } from "@/src/format";
import { Button, Empty, Field, FONT_DISPLAY, FONT_TEXT, Stepper } from "@/src/components/ui";

export default function CartScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t, tx } = useI18n();
  const cart = useCart();
  const { data } = useMenu();
  const settings = data?.settings;
  const goods = cart.subtotal + cart.extrasTotal;

  return (
    <View style={styles.screen}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Text style={styles.title} testID="cart-title">{t("cart")}</Text>
        {cart.items.length > 0 ? <Text style={styles.count}>{cart.count} {t("items").toLowerCase()}</Text> : null}
      </View>

      {cart.items.length === 0 ? (
        <Empty icon="shopping-bag" title={t("emptyCart")} hint={t("emptyCartHint")} action={<Button title={t("browseMenu")} onPress={() => router.push("/(tabs)")} testID="cart-browse-menu-button" />} />
      ) : (
        <>
          <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, paddingBottom: 200 }} bottomOffset={220} showsVerticalScrollIndicator={false}>
            {cart.items.map((it) => (
              <View key={it.line_id} style={styles.item} testID={`cart-item-${it.line_id}`}>
                <Image source={{ uri: it.image_url || undefined }} style={styles.img} contentFit="cover" />
                <View style={{ flex: 1 }}>
                  <View style={styles.itemHead}>
                    <Text style={styles.itemName} numberOfLines={1}>{tx(it.name)}{it.size ? ` · ${it.size.label}` : ""}</Text>
                    <Text style={styles.itemPrice}>{chf(lineTotal(it))}</Text>
                  </View>
                  {it.options.map((o) => (
                    <Text key={o.key} style={styles.extra}>• {tx(o.name)}{o.price > 0 ? ` (+${chf(o.price)})` : ""}</Text>
                  ))}
                  {it.removed_ingredients.map((r) => (
                    <Text key={r.id} style={styles.removed}>− {t("without")} {tx(r)}</Text>
                  ))}
                  {it.extras.map((e) => (
                    <Text key={e.extra_id} style={styles.extra}>+ {e.quantity > 1 ? `${e.quantity}x ` : ""}{tx(e.name)} ({chf(e.unit_price * e.quantity)})</Text>
                  ))}
                  {it.note ? <Text style={styles.note}>« {it.note} »</Text> : null}
                  <View style={styles.itemActions}>
                    <Stepper value={it.quantity} size={32} onChange={(v) => cart.updateItem(it.line_id, { quantity: v })} testID={`cart-qty-${it.line_id}`} />
                    <View style={{ flexDirection: "row", gap: 6 }}>
                      <Pressable testID={`cart-edit-${it.line_id}`} onPress={() => router.push({ pathname: "/product/[id]", params: { id: it.product_id, line: it.line_id } })} style={styles.iconBtn} hitSlop={6}>
                        <Feather name="edit-2" size={16} color={colors.onSurface} />
                      </Pressable>
                      <Pressable testID={`cart-remove-${it.line_id}`} onPress={() => cart.removeItem(it.line_id)} style={styles.iconBtn} hitSlop={6}>
                        <Feather name="trash-2" size={16} color={colors.error} />
                      </Pressable>
                    </View>
                  </View>
                </View>
              </View>
            ))}

            <View style={{ marginTop: 8 }}>
              <Field label={t("orderNote")} placeholder={t("orderNotePlaceholder")} value={cart.generalNote} onChangeText={cart.setGeneralNote} multiline testID="cart-general-note-input" />
            </View>

            <View style={styles.summary}>
              <Row label={t("subtotal")} value={chf(cart.subtotal)} />
              <Row label={t("extrasTotal")} value={chf(cart.extrasTotal)} />
              {settings?.delivery_enabled ? (
                <Row label={`${t("deliveryFee")} (${t("delivery").toLowerCase()})`} value={settings.free_delivery_from && goods >= settings.free_delivery_from ? t("free") : chf(settings.delivery_fee)} muted />
              ) : null}
              <View style={styles.divider} />
              <View style={styles.row}>
                <Text style={styles.totalLabel}>{t("total")}</Text>
                <Text style={styles.totalValue} testID="cart-total">{chf(goods)}</Text>
              </View>
              <Text style={styles.paymentHint}>{t("noOnlinePayment")}</Text>
            </View>
          </KeyboardAwareScrollView>

          <View style={[styles.cta, { paddingBottom: 16 }]}>
            <Button title={`${t("checkout")} · ${chf(goods)}`} size="lg" icon="arrow-right" onPress={() => router.push("/checkout")} testID="cart-checkout-button" />
          </View>
        </>
      )}
    </View>
  );
}

function Row({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  const styles = useStyles();
  return (
    <View style={styles.row}>
      <Text style={[styles.rowLabel, muted && { opacity: 0.7 }]}>{label}</Text>
      <Text style={[styles.rowValue, muted && { opacity: 0.7 }]}>{value}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: 16, paddingBottom: 12, flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.surface },
  title: { fontFamily: FONT_DISPLAY, fontSize: 28, color: colors.onSurface },
  count: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.muted },
  item: { flexDirection: "row", gap: 12, backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 12, marginBottom: 12 },
  img: { width: 72, height: 72, borderRadius: 12, backgroundColor: colors.surfaceTertiary },
  itemHead: { flexDirection: "row", justifyContent: "space-between", gap: 8 },
  itemName: { fontFamily: FONT_DISPLAY, fontSize: 17, color: colors.onSurface, flex: 1 },
  itemPrice: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "700", color: colors.onSurface },
  removed: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.error, marginTop: 2 },
  extra: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.brandSecondary, marginTop: 2 },
  note: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, fontStyle: "italic", marginTop: 2 },
  itemActions: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 10 },
  iconBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  summary: { marginTop: 20, backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 8 },
  row: { flexDirection: "row", justifyContent: "space-between" },
  rowLabel: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary },
  rowValue: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurface, fontWeight: "600" },
  divider: { height: 1, backgroundColor: colors.divider, marginVertical: 4 },
  totalLabel: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  totalValue: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.brandPrimary },
  paymentHint: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, marginTop: 4 },
  cta: { position: "absolute", left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 12, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
}));
