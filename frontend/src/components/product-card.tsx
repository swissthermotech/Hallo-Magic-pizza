import React from "react";
import { Pressable, Text, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import Animated, { FadeInUp } from "react-native-reanimated";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useCart } from "@/src/cart";
import { imgUri } from "@/src/api";
import { chf } from "@/src/format";
import { FONT_DISPLAY, FONT_TEXT, useToast } from "./ui";
import type { Product } from "@/src/types";

/**
 * Editorial, image-first product card.
 * - Customisable products open the detail page ("Personnaliser").
 * - Simple products can be added directly ("Ajouter").
 */
export function ProductCard({ product, onPress, index = 0 }: { product: Product; onPress: () => void; index?: number }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t, tx } = useI18n();
  const cart = useCart();
  const toast = useToast();
  const off = !product.available;
  const hasSizes = product.sizes.length > 1;
  const price = product.sizes[0]?.price ?? product.price;

  const quickAdd = () => {
    if (off) return;
    if (product.customizable || hasSizes) return onPress();
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    cart.addItem({
      product_id: product.id, name: product.name, image_url: product.image_url, unit_price: price, quantity: 1,
      size: product.sizes[0] ?? null, options: [], removed_ingredients: [], extras: [], note: "", is_alcohol: product.is_alcohol, alcohol_type: product.alcohol_type,
    });
    toast.show(`${tx(product.name)} – ${t("added")}`, "success");
  };

  return (
    <Animated.View entering={FadeInUp.delay(Math.min(index, 6) * 50).duration(400)} style={styles.wrap}>
      <Pressable testID={`product-card-${product.id}`} onPress={onPress} style={({ pressed }) => [styles.imgWrap, pressed && { transform: [{ scale: 0.985 }] }]}>
        <Image source={{ uri: imgUri(product.image_url) }} style={styles.img} contentFit="cover" transition={300} />
        <LinearGradient colors={[colors.scrimTransparent, colors.scrim]} start={{ x: 0.5, y: 0.35 }} end={{ x: 0.5, y: 1 }} style={styles.scrim} />
        <View style={styles.topBadges}>
          {product.highlight === "moment" ? (
            <View style={styles.pillBrand} testID={`product-month-${product.id}`}>
              <Feather name="star" size={11} color={colors.onBrandPrimary} />
              <Text style={styles.pillBrandText}>{t("pizzaOfMonth")}</Text>
            </View>
          ) : null}
          {product.is_alcohol ? <View style={styles.pillDark}><Text style={styles.pillDarkText}>{product.alcohol_type === "spirits" ? "18+" : "16+"}</Text></View> : null}
          {product.customizable ? (
            <View style={styles.pillDark}>
              <Feather name="sliders" size={11} color={colors.onSurfaceInverse} />
              <Text style={styles.pillDarkText}>{t("customize")}</Text>
            </View>
          ) : null}
        </View>
        <View style={styles.overlayBottom}>
          <Text style={styles.name} numberOfLines={1} testID={`product-name-${product.id}`}>{tx(product.name)}</Text>
          <View style={styles.pricePill}>
            <Text style={styles.priceText} testID={`product-price-${product.id}`}>{hasSizes ? `${t("from")} ` : ""}{chf(price)}</Text>
          </View>
        </View>
        {off ? (
          <View style={styles.soldOut}>
            <Text style={styles.soldOutText}>{t("soldOut")}</Text>
          </View>
        ) : null}
      </Pressable>
      <View style={styles.body}>
        <Text style={styles.desc} numberOfLines={2}>{tx(product.description)}</Text>
        <View style={styles.actions}>
          {product.customizable || hasSizes ? (
            <Pressable testID={`product-customize-${product.id}`} onPress={onPress} disabled={off} style={({ pressed }) => [styles.secondaryBtn, pressed && { opacity: 0.8 }, off && { opacity: 0.4 }]}>
              <Feather name="sliders" size={15} color={colors.onSurface} />
              <Text style={styles.secondaryText}>{t("customize")}</Text>
            </Pressable>
          ) : <View style={{ flex: 1 }} />}
          <Pressable testID={`product-add-${product.id}`} onPress={quickAdd} disabled={off} style={({ pressed }) => [styles.primaryBtn, pressed && { opacity: 0.85, transform: [{ scale: 0.97 }] }, off && { opacity: 0.4 }]}>
            <Feather name="plus" size={16} color={colors.onBrandPrimary} />
            <Text style={styles.primaryText}>{product.customizable || hasSizes ? t("orderNow") : t("add")}</Text>
          </Pressable>
        </View>
      </View>
    </Animated.View>
  );
}

const useStyles = makeStyles((colors) => ({
  wrap: { marginBottom: 28 },
  imgWrap: { height: 210, borderRadius: 24, overflow: "hidden", backgroundColor: colors.surfaceTertiary, shadowColor: colors.surfaceInverse, shadowOpacity: 0.12, shadowRadius: 16, shadowOffset: { width: 0, height: 8 }, elevation: 4 },
  img: { width: "100%", height: "100%" },
  scrim: { position: "absolute", left: 0, right: 0, top: 0, bottom: 0 },
  topBadges: { position: "absolute", top: 12, left: 12, flexDirection: "row", gap: 6 },
  pillDark: { flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: colors.overlay, borderRadius: 999, paddingHorizontal: 10, height: 26 },
  pillDarkText: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "800", color: colors.onSurfaceInverse, letterSpacing: 0.4 },
  pillBrand: { flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: colors.brandPrimary, borderRadius: 999, paddingHorizontal: 10, height: 26 },
  pillBrandText: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "900", color: colors.onBrandPrimary, letterSpacing: 0.8 },
  overlayBottom: { position: "absolute", left: 16, right: 16, bottom: 14, flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", gap: 10 },
  name: { fontFamily: FONT_DISPLAY, fontSize: 24, color: colors.onSurfaceInverse, flex: 1 },
  pricePill: { backgroundColor: colors.surface, borderRadius: 999, paddingHorizontal: 12, height: 32, justifyContent: "center" },
  priceText: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "800", color: colors.onSurface },
  soldOut: { position: "absolute", left: 0, right: 0, top: 0, bottom: 0, backgroundColor: colors.overlay, alignItems: "center", justifyContent: "center" },
  soldOutText: { fontFamily: FONT_TEXT, color: colors.onSurfaceInverse, fontWeight: "800", fontSize: 14, letterSpacing: 2, textTransform: "uppercase", borderWidth: 1.5, borderColor: colors.onSurfaceInverse, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999 },
  body: { paddingHorizontal: 4, paddingTop: 12, gap: 12 },
  desc: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.muted, lineHeight: 20 },
  actions: { flexDirection: "row", alignItems: "center", gap: 10 },
  secondaryBtn: { flex: 1, height: 46, borderRadius: 999, borderWidth: 1.5, borderColor: colors.borderStrong, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, backgroundColor: colors.surfaceSecondary },
  secondaryText: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "700", color: colors.onSurface },
  primaryBtn: { flex: 1, height: 46, borderRadius: 999, backgroundColor: colors.brandPrimary, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6 },
  primaryText: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "800", color: colors.onBrandPrimary, letterSpacing: 0.3 },
}));
