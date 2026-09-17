import React, { useMemo, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { imgUri, useMenu } from "@/src/api";
import { useCart } from "@/src/cart";
import { chf } from "@/src/format";
import { FONT_TEXT, useToast } from "@/src/components/ui";
import type { Product } from "@/src/types";
import { HalfHalfPicker } from "@/src/components/phone/half-half";

/** Step 2: fast product entry from the shared menu. Simple products are added with one tap,
 * pizzas / customizable products open the existing product sheet (size, dough, extras, removals, note). */
export function MenuPanel() {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const cart = useCart();
  const { data } = useMenu();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<string>("all");
  const [half, setHalf] = useState(false);

  const products = useMemo(() => {
    if (!data) return [];
    const needle = q.trim().toLowerCase();
    let list = [...data.products];
    if (needle) list = list.filter((p) => p.name.fr.toLowerCase().includes(needle) || p.name.de.toLowerCase().includes(needle) || p.description.fr.toLowerCase().includes(needle));
    else if (cat !== "all") {
      const c = data.categories.find((x) => x.id === cat);
      list = c?.filter ? list.filter((p) => p.options.some((o) => o.key === c.filter)) : list.filter((p) => p.category_id === cat);
    }
    return list;
  }, [data, q, cat]);

  const add = (p: Product) => {
    if (!p.available) return;
    if (p.customizable || p.sizes.length > 1) {
      router.push({ pathname: "/product/[id]", params: { id: p.id } });
      return;
    }
    Haptics.selectionAsync().catch(() => {});
    const existing = cart.items.find((i) => i.product_id === p.id && !i.extras.length && !i.removed_ingredients.length && !i.note && !i.options.length);
    if (existing) cart.updateItem(existing.line_id, { quantity: existing.quantity + 1 });
    else cart.addItem({ product_id: p.id, name: p.name, image_url: p.image_url, unit_price: p.sizes[0]?.price ?? p.price, quantity: 1, size: p.sizes[0] ?? null, options: [], removed_ingredients: [], extras: [], note: "", is_alcohol: p.is_alcohol, alcohol_type: p.alcohol_type });
    toast.show(`${p.name.fr} – ${t("added")}`, "success");
  };

  return (
    <View style={{ gap: 12 }}>
      <View style={styles.searchWrap}>
        <Feather name="search" size={20} color={colors.muted} />
        <TextInput testID="phone-menu-search" value={q} onChangeText={setQ} placeholder={t("searchProducts")} placeholderTextColor={colors.muted} style={styles.searchInput} autoCorrect={false} />
        {q ? <Pressable onPress={() => setQ("")} hitSlop={8}><Feather name="x" size={18} color={colors.muted} /></Pressable> : null}
      </View>
      <HalfHalfPicker visible={half} onClose={() => setHalf(false)} />
      <View style={styles.chips}>
        <Pressable testID="phone-half-half" onPress={() => setHalf(true)} style={[styles.chip, styles.chipHalf]}><Text style={[styles.chipText, styles.chipTextOn]}>½ / ½ {t("halfHalf")}</Text></Pressable>
        <Pressable testID="phone-cat-all" onPress={() => setCat("all")} style={[styles.chip, cat === "all" && styles.chipOn]}><Text style={[styles.chipText, cat === "all" && styles.chipTextOn]}>{t("all")}</Text></Pressable>
        {data?.categories.map((c) => (
          <Pressable key={c.id} testID={`phone-cat-${c.slug}`} onPress={() => { setCat(c.id); setQ(""); }} style={[styles.chip, cat === c.id && styles.chipOn]}><Text style={[styles.chipText, cat === c.id && styles.chipTextOn]}>{c.name.fr}</Text></Pressable>
        ))}
      </View>
      <View style={styles.grid}>
        {products.map((p) => {
          const inCart = cart.items.filter((i) => i.product_id === p.id).reduce((s, i) => s + i.quantity, 0);
          const price = p.sizes[0]?.price ?? p.price;
          return (
            <Pressable key={p.id} testID={`phone-product-${p.id}`} onPress={() => add(p)} disabled={!p.available} style={({ pressed }) => [styles.tile, pressed && { opacity: 0.85, transform: [{ scale: 0.98 }] }, !p.available && { opacity: 0.4 }]}>
              <Image source={{ uri: imgUri(p.image_url) }} style={styles.thumb} contentFit="cover" />
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={styles.tileName} numberOfLines={1}>{p.name.fr}</Text>
                <Text style={styles.tileMeta} numberOfLines={1}>{p.sizes.length > 1 ? `${t("from")} ${chf(price)} · ${p.sizes.map((s) => s.label).join("/")}` : chf(price)}{p.is_alcohol ? ` · ${p.alcohol_type === "spirits" ? 18 : 16}+` : ""}</Text>
              </View>
              <View style={[styles.addBtn, inCart > 0 && styles.addBtnOn]}>
                {inCart > 0 ? <Text style={styles.addCount}>{inCart}</Text> : <Feather name={p.customizable || p.sizes.length > 1 ? "sliders" : "plus"} size={18} color={colors.onBrandPrimary} />}
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  searchWrap: { flexDirection: "row", alignItems: "center", gap: 10, height: 56, borderRadius: 16, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 16 },
  searchInput: { flex: 1, fontFamily: FONT_TEXT, fontSize: 18, fontWeight: "600", color: colors.onSurface, height: 56 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { height: 40, paddingHorizontal: 16, borderRadius: 999, backgroundColor: colors.surfaceTertiary, justifyContent: "center" },
  chipOn: { backgroundColor: colors.brandPrimary },
  chipHalf: { backgroundColor: colors.surfaceInverse },
  chipText: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "700", color: colors.onSurfaceTertiary },
  chipTextOn: { color: colors.onBrandPrimary },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  tile: { width: "48.5%", flexGrow: 1, minWidth: 260, flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 10, minHeight: 72 },
  thumb: { width: 52, height: 52, borderRadius: 12, backgroundColor: colors.surfaceTertiary },
  tileName: { fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "800", color: colors.onSurface },
  tileMeta: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  addBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" },
  addBtnOn: { backgroundColor: colors.success },
  addCount: { fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "900", color: colors.onBrandPrimary },
}));
