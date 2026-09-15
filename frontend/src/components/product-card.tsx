import React from "react";
import { Pressable, Text, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@react-native-vector-icons/feather";
import Animated, { FadeInUp } from "react-native-reanimated";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { chf } from "@/src/format";
import { FONT_DISPLAY, FONT_TEXT, Badge } from "./ui";
import type { Product } from "@/src/types";

export function ProductCard({ product, onPress, index = 0 }: { product: Product; onPress: () => void; index?: number }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t, tx } = useI18n();
  const off = !product.available;
  return (
    <Animated.View entering={FadeInUp.delay(Math.min(index, 8) * 40).duration(350)}>
      <Pressable testID={`product-card-${product.id}`} onPress={onPress} style={({ pressed }) => [styles.card, pressed && { transform: [{ scale: 0.985 }] }, off && { opacity: 0.6 }]}>
        <View style={styles.imgWrap}>
          <Image source={{ uri: product.image_url || undefined }} style={styles.img} contentFit="cover" transition={200} />
          {off ? (
            <View style={styles.soldOut}>
              <Text style={styles.soldOutText}>{t("soldOut")}</Text>
            </View>
          ) : null}
        </View>
        <View style={styles.body}>
          <View style={styles.titleRow}>
            <Text style={styles.name} numberOfLines={1} testID={`product-name-${product.id}`}>{tx(product.name)}</Text>
            {product.is_alcohol ? <Badge label="18+" tone="warning" /> : null}
          </View>
          <Text style={styles.desc} numberOfLines={2}>{tx(product.description)}</Text>
          <View style={styles.footer}>
            <Text style={styles.price} testID={`product-price-${product.id}`}>{product.sizes.length > 1 ? `${t("from")} ` : ""}{chf(product.sizes[0]?.price ?? product.price)}</Text>
            {product.customizable ? (
              <View style={styles.custom}>
                <Feather name="sliders" size={12} color={colors.brandSecondary} />
                <Text style={styles.customText}>{t("customize")}</Text>
              </View>
            ) : null}
            <View style={styles.addBtn}>
              <Feather name="plus" size={18} color={colors.onBrandPrimary} />
            </View>
          </View>
        </View>
      </Pressable>
    </Animated.View>
  );
}

const useStyles = makeStyles((colors) => ({
  card: { flexDirection: "row", backgroundColor: colors.surfaceSecondary, borderRadius: 20, borderWidth: 1, borderColor: colors.border, overflow: "hidden", marginBottom: 12, shadowColor: colors.surfaceInverse, shadowOpacity: 0.05, shadowRadius: 10, shadowOffset: { width: 0, height: 4 }, elevation: 1 },
  imgWrap: { width: 116, height: 128, backgroundColor: colors.surfaceTertiary },
  img: { width: "100%", height: "100%" },
  soldOut: { position: "absolute", inset: 0, backgroundColor: colors.overlay, alignItems: "center", justifyContent: "center" },
  soldOutText: { fontFamily: FONT_TEXT, color: colors.onSurfaceInverse, fontWeight: "800", fontSize: 12, letterSpacing: 1, textTransform: "uppercase" },
  body: { flex: 1, padding: 12, justifyContent: "space-between" },
  titleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  name: { fontFamily: FONT_DISPLAY, fontSize: 18, color: colors.onSurface, flex: 1 },
  desc: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, lineHeight: 18, marginTop: 4 },
  footer: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 8 },
  price: { fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "800", color: colors.onSurface, flex: 1 },
  custom: { flexDirection: "row", alignItems: "center", gap: 4 },
  customText: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.brandSecondary, fontWeight: "600" },
  addBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" },
}));
