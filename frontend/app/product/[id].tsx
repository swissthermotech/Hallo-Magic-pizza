import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView, KeyboardStickyView } from "react-native-keyboard-controller";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { imgUri, useMenu } from "@/src/api";
import { useCart } from "@/src/cart";
import { chf } from "@/src/format";
import { Badge, Button, Chip, Field, FONT_DISPLAY, FONT_TEXT, Stepper, useToast } from "@/src/components/ui";
import type { CartExtra, Ingredient, ProductOption } from "@/src/types";

export default function ProductScreen() {
  const { id, line, option } = useLocalSearchParams<{ id: string; line?: string; option?: string }>();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t, tx } = useI18n();
  const toast = useToast();
  const { data, isLoading } = useMenu();
  const cart = useCart();

  const product = data?.products.find((p) => p.id === id);
  const editing = line ? cart.items.find((i) => i.line_id === line) : undefined;

  const [qty, setQty] = useState(1);
  const [sizeKey, setSizeKey] = useState<string | null>(null);
  const [optKeys, setOptKeys] = useState<string[]>([]);
  const [removed, setRemoved] = useState<Ingredient[]>([]);
  const [extras, setExtras] = useState<CartExtra[]>([]);
  const [note, setNote] = useState("");

  // Initialise defaults once the product is known
  useEffect(() => {
    if (!product) return;
    if (editing) {
      setQty(editing.quantity);
      setSizeKey(editing.size?.key ?? null);
      setOptKeys(editing.options.map((o) => o.key));
      setRemoved(editing.removed_ingredients);
      setExtras(editing.extras);
      setNote(editing.note);
      return;
    }
    setSizeKey(product.sizes[0]?.key ?? null);
    const defaults = product.options.filter((o) => o.default).map((o) => o.key);
    if (option && product.options.some((o) => o.key === option)) {
      const chosen = product.options.find((o) => o.key === option)!;
      setOptKeys([...defaults.filter((k) => product.options.find((o) => o.key === k)?.group !== chosen.group), option]);
      if (chosen.only_sizes.length) setSizeKey(chosen.only_sizes[0]);
    } else setOptKeys(defaults);
  }, [product?.id, editing?.line_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const size = product?.sizes.find((s) => s.key === sizeKey) ?? product?.sizes[0] ?? null;
  const optionPrice = (o: ProductOption) => (size && o.price_by_size[size.key] !== undefined ? o.price_by_size[size.key] : o.price);
  const optionAllowed = (o: ProductOption) => !o.only_sizes.length || !size || o.only_sizes.includes(size.key);
  const groups = useMemo(() => {
    const g: Record<string, ProductOption[]> = {};
    product?.options.forEach((o) => (g[o.group] = [...(g[o.group] || []), o]));
    return g;
  }, [product]);

  const allowedExtras = useMemo(() => {
    if (!product || !data) return [];
    const allowed = new Set(product.allowed_extra_ids);
    return data.extras.filter((e) => e.available && (allowed.has(e.key) || allowed.has(e.id)));
  }, [product, data]);

  const selectedOptions = (product?.options || []).filter((o) => optKeys.includes(o.key) && !o.default && optionAllowed(o));
  const basePrice = size ? size.price : product?.price ?? 0;
  const optionsSum = selectedOptions.reduce((s, o) => s + optionPrice(o), 0);
  const extrasSum = extras.reduce((s, e) => s + e.unit_price * e.quantity, 0);
  const unit = basePrice + optionsSum;
  const total = (unit + extrasSum) * qty;

  const selectSize = (k: string) => {
    Haptics.selectionAsync().catch(() => {});
    setSizeKey(k);
    // drop options that are not available for the new size, fall back to group default
    setOptKeys((prev) => {
      const next = prev.filter((key) => {
        const o = product?.options.find((x) => x.key === key);
        return !o || !o.only_sizes.length || o.only_sizes.includes(k);
      });
      Object.values(groups).forEach((list) => {
        if (list.length && !list.some((o) => next.includes(o.key))) {
          const d = list.find((o) => o.default);
          if (d) next.push(d.key);
        }
      });
      return next;
    });
  };
  const chooseOption = (o: ProductOption, list: ProductOption[]) => {
    Haptics.selectionAsync().catch(() => {});
    const radio = list.some((x) => x.default); // groups with a default behave like radio buttons
    setOptKeys((prev) => {
      if (radio) return [...prev.filter((k) => !list.some((x) => x.key === k)), o.key];
      return prev.includes(o.key) ? prev.filter((k) => k !== o.key) : [...prev, o.key];
    });
    if (o.only_sizes.length && size && !o.only_sizes.includes(size.key)) setSizeKey(o.only_sizes[0]);
  };
  const toggleIngredient = (ing: Ingredient) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    setRemoved((prev) => (prev.some((r) => r.id === ing.id) ? prev.filter((r) => r.id !== ing.id) : [...prev, ing]));
  };
  const setExtraQty = (e: { id: string; key: string; name: { fr: string; de: string }; price: number }, q: number) => {
    setExtras((prev) => {
      const rest = prev.filter((x) => x.extra_id !== e.id);
      return q <= 0 ? rest : [...rest, { extra_id: e.id, key: e.key, name: e.name, unit_price: e.price, quantity: q }];
    });
  };

  const submit = () => {
    if (!product) return;
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    const payload = {
      product_id: product.id,
      name: product.name,
      image_url: product.image_url,
      unit_price: unit,
      quantity: qty,
      size,
      options: selectedOptions.map((o) => ({ key: o.key, name: o.name, price: optionPrice(o) })),
      removed_ingredients: removed,
      extras,
      note: note.trim(),
      is_alcohol: product.is_alcohol,
      alcohol_type: product.alcohol_type,
    };
    if (editing) cart.updateItem(editing.line_id, payload);
    else cart.addItem(payload);
    toast.show(`${tx(product.name)} – ${t("added")}`, "success");
    router.back();
  };

  if (isLoading || !data) {
    return (
      <View style={[styles.screen, styles.center]}>
        <ActivityIndicator color={colors.brandPrimary} size="large" />
      </View>
    );
  }
  if (!product) {
    return (
      <View style={[styles.screen, styles.center]}>
        <Text style={styles.muted}>{t("unavailable")}</Text>
        <Button title={t("back")} variant="outline" onPress={() => router.back()} />
      </View>
    );
  }

  const CTA_H = 96 + insets.bottom;
  const isCustom = product.ingredients.length <= 3 && allowedExtras.length > 10 && product.customizable;

  return (
    <View style={styles.screen}>
      <KeyboardAwareScrollView contentContainerStyle={{ paddingBottom: CTA_H + 16 }} bottomOffset={CTA_H + 16} showsVerticalScrollIndicator={false}>
        <View style={styles.hero}>
          <Image source={{ uri: imgUri(product.image_url) }} style={styles.heroImg} contentFit="cover" transition={250} />
          <LinearGradient colors={[colors.scrimTransparent, colors.scrim]} style={styles.heroScrim} />
          <Pressable testID="product-close-button" onPress={() => router.back()} style={[styles.closeBtn, { top: insets.top + 8 }]} hitSlop={8}>
            <Feather name="x" size={20} color={colors.onSurface} />
          </Pressable>
          <View style={styles.heroText}>
            <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
              {product.is_alcohol ? <Badge label={`${product.alcohol_type === "spirits" ? 18 : 16}+`} tone="warning" /> : null}
              {!product.available ? <Badge label={t("soldOut")} tone="error" /> : null}
            </View>
            <Text style={styles.name} testID="product-detail-name">{tx(product.name)}</Text>
            <Text style={styles.basePrice}>{product.sizes.length > 1 ? `${t("from")} ` : ""}{chf(product.sizes[0]?.price ?? product.price)}</Text>
          </View>
        </View>

        <View style={styles.content}>
          <Text style={styles.desc} testID="product-detail-description">{tx(product.description)}</Text>

          {product.wine ? (
            <View style={styles.infoRow}>
              {product.wine.origin ? <Text style={styles.infoText}>{t("origin")}: {product.wine.origin}</Text> : null}
              {product.wine.bottle_size ? <Text style={styles.infoText}>{t("bottle")}: {product.wine.bottle_size}</Text> : null}
            </View>
          ) : null}

          <View style={styles.allergenBox}>
            <Feather name="info" size={14} color={colors.muted} />
            <Text style={styles.allergenText}>{t("allergens")}: {tx(product.allergens) || t("notConfigured")}</Text>
            {tx(product.origin) ? <Text style={styles.allergenText} testID="product-origin">{t("origin")}: {tx(product.origin)}</Text> : null}
          </View>

          {/* Sizes */}
          {product.sizes.length > 1 ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>{t("size")}</Text>
              <View style={styles.sizeRow}>
                {product.sizes.map((s) => {
                  const on = size?.key === s.key;
                  return (
                    <Pressable key={s.key} testID={`size-option-${s.key}`} onPress={() => selectSize(s.key)} style={[styles.sizeCard, on && styles.sizeCardOn]}>
                      <Text style={[styles.sizeLabel, on && styles.sizeLabelOn]}>{s.label}</Text>
                      <Text style={[styles.sizePrice, on && styles.sizeLabelOn]}>{chf(s.price)}</Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ) : null}

          {/* Dough & options */}
          {Object.entries(groups).map(([group, list]) => (
            <View key={group} style={styles.section}>
              <Text style={styles.sectionTitle}>{group === "dough" ? t("dough") : t("options")}</Text>
              <View style={styles.extraList}>
                {list.map((o, i) => {
                  const on = optKeys.includes(o.key);
                  const ok = optionAllowed(o);
                  const p = optionPrice(o);
                  return (
                    <Pressable key={o.key} testID={`option-${o.key}`} onPress={() => chooseOption(o, list)} style={[styles.extraRow, i < list.length - 1 && styles.extraRowBorder, !ok && { opacity: 0.45 }]}>
                      <View style={[styles.radio, on && styles.radioOn]}>{on ? <Feather name="check" size={14} color={colors.onBrandPrimary} /> : null}</View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.extraName}>{tx(o.name)}</Text>
                        {o.only_sizes.length ? <Text style={styles.extraPrice}>{o.only_sizes.map((k) => product.sizes.find((s) => s.key === k)?.label ?? k).join(", ")}</Text> : null}
                      </View>
                      <Text style={styles.optPrice}>{p > 0 ? `+ ${chf(p)}` : ""}</Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ))}

          {product.customizable && product.ingredients.length > 0 && !isCustom ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>{t("removeIngredients")}</Text>
              <Text style={styles.hint}>{t("removeHint")}</Text>
              <View style={styles.wrapChips}>
                {product.ingredients.map((ing) => (
                  <Chip key={ing.id} label={tx(ing)} tone="danger" selected={removed.some((r) => r.id === ing.id)} onPress={() => toggleIngredient(ing)} testID={`ingredient-chip-${ing.id}`} />
                ))}
              </View>
            </View>
          ) : null}

          {product.customizable && allowedExtras.length > 0 ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>{isCustom ? t("ingredients") : t("extras")}</Text>
              <View style={styles.extraList}>
                {allowedExtras.map((e, i) => {
                  const cur = extras.find((x) => x.extra_id === e.id)?.quantity ?? 0;
                  return (
                    <View key={e.id} style={[styles.extraRow, i < allowedExtras.length - 1 && styles.extraRowBorder]} testID={`extra-row-${e.key}`}>
                      <View style={{ flex: 1 }}>
                        <Text style={[styles.extraName, cur > 0 && { color: colors.brandSecondary }]}>{tx(e.name)}</Text>
                        <Text style={styles.extraPrice}>+ {chf(e.price)}</Text>
                      </View>
                      {cur === 0 ? (
                        <Pressable testID={`extra-add-${e.key}`} onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {}); setExtraQty(e, 1); }} style={styles.extraAdd}>
                          <Feather name="plus" size={18} color={colors.onSurface} />
                        </Pressable>
                      ) : (
                        <Stepper value={cur} min={0} max={e.max_quantity} size={32} onChange={(v) => setExtraQty(e, v)} testID={`extra-stepper-${e.key}`} />
                      )}
                    </View>
                  );
                })}
              </View>
            </View>
          ) : null}

          {product.customizable ? (
            <View style={styles.section}>
              <Field label={t("kitchenNote")} placeholder={t("kitchenNotePlaceholder")} value={note} onChangeText={setNote} multiline testID="product-note-input" />
            </View>
          ) : null}

          <View style={[styles.section, styles.qtyRow]}>
            <Text style={styles.sectionTitle}>{t("quantity")}</Text>
            <Stepper value={qty} onChange={setQty} size={40} testID="product-qty-stepper" />
          </View>
        </View>
      </KeyboardAwareScrollView>

      <KeyboardStickyView offset={{ closed: 0, opened: insets.bottom }}>
        <View style={[styles.cta, { paddingBottom: insets.bottom + 12 }]}>
          <View style={{ flex: 1 }}>
            <Text style={styles.ctaLabel}>{t("total")}{size ? ` · ${size.label}` : ""}</Text>
            <Text style={styles.ctaPrice} testID="product-live-total">{chf(total)}</Text>
            {extrasSum + optionsSum > 0 ? <Text style={styles.ctaExtras}>+ {chf(extrasSum + optionsSum)} {t("options").toLowerCase()} / {t("each")}</Text> : null}
          </View>
          <Button title={editing ? t("save") : t("addToCart")} icon="shopping-bag" size="lg" onPress={submit} disabled={!product.available} style={{ flex: 1.4 }} testID="add-to-cart-button" />
        </View>
      </KeyboardStickyView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  center: { alignItems: "center", justifyContent: "center", gap: 16 },
  muted: { fontFamily: FONT_TEXT, color: colors.muted, fontSize: 16 },
  hero: { height: 400, backgroundColor: colors.surfaceTertiary },
  heroImg: { width: "100%", height: "100%" },
  heroScrim: { position: "absolute", left: 0, right: 0, top: 0, bottom: 0 },
  closeBtn: { position: "absolute", left: 16, width: 42, height: 42, borderRadius: 21, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center", shadowColor: colors.surfaceInverse, shadowOpacity: 0.2, shadowRadius: 8, shadowOffset: { width: 0, height: 4 }, elevation: 3 },
  heroText: { position: "absolute", left: 22, right: 22, bottom: 44 },
  name: { fontFamily: FONT_DISPLAY, fontSize: 38, color: colors.onSurfaceInverse, lineHeight: 44 },
  basePrice: { fontFamily: FONT_TEXT, fontSize: 18, fontWeight: "700", color: colors.onSurfaceInverse, marginTop: 6, opacity: 0.9 },
  content: { padding: 22, paddingTop: 26, gap: 4, marginTop: -28, backgroundColor: colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28 },
  desc: { fontFamily: FONT_TEXT, fontSize: 16, color: colors.onSurfaceSecondary, lineHeight: 24 },
  infoRow: { flexDirection: "row", gap: 16, marginTop: 8, flexWrap: "wrap" },
  infoText: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  allergenBox: { flexDirection: "row", gap: 8, alignItems: "center", backgroundColor: colors.surfaceTertiary, borderRadius: 12, padding: 12, marginTop: 14 },
  allergenText: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.onSurfaceTertiary, flex: 1 },
  section: { marginTop: 24 },
  sectionTitle: { fontFamily: FONT_DISPLAY, fontSize: 21, color: colors.onSurface },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, marginTop: 4, marginBottom: 12 },
  wrapChips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  sizeRow: { flexDirection: "row", gap: 10, marginTop: 12 },
  sizeCard: { flex: 1, height: 76, borderRadius: 18, borderWidth: 1.5, borderColor: colors.border, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center", gap: 2 },
  sizeCardOn: { borderColor: colors.surfaceInverse, backgroundColor: colors.surfaceInverse },
  sizeLabel: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  sizeLabelOn: { color: colors.onSurfaceInverse },
  sizePrice: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.muted },
  radio: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center" },
  radioOn: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  optPrice: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "700", color: colors.onSurface },
  extraList: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, marginTop: 12 },
  extraRow: { flexDirection: "row", alignItems: "center", paddingHorizontal: 14, paddingVertical: 10, minHeight: 56, gap: 12 },
  extraRowBorder: { borderBottomWidth: 1, borderBottomColor: colors.divider },
  extraName: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "600", color: colors.onSurface },
  extraPrice: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, marginTop: 2 },
  extraAdd: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  qtyRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  cta: { position: "absolute", left: 0, right: 0, bottom: 0, flexDirection: "row", alignItems: "center", gap: 16, paddingHorizontal: 20, paddingTop: 14, backgroundColor: colors.surfaceSecondary, borderTopWidth: 1, borderTopColor: colors.border },
  ctaLabel: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  ctaPrice: { fontFamily: FONT_DISPLAY, fontSize: 26, color: colors.onSurface },
  ctaExtras: { fontFamily: FONT_TEXT, fontSize: 11, color: colors.brandSecondary },
}));
