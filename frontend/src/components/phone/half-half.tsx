import React, { useMemo, useState } from "react";
import { Modal, Pressable, ScrollView, Text, View } from "react-native";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu } from "@/src/api";
import { useCart } from "@/src/cart";
import { chf } from "@/src/format";
import { Button, Chip, Field, FONT_DISPLAY, FONT_TEXT, useToast } from "@/src/components/ui";
import type { Ingredient, Product } from "@/src/types";

/** MOITIÉ / MOITIÉ pizza – staff phone orders only. Price = the more expensive of the two pizzas (+ extras added later via edit). */
export function HalfHalfPicker({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const cart = useCart();
  const { data } = useMenu();
  const pizzas = useMemo(() => (data?.products ?? []).filter((p) => p.sizes.length > 1 && p.available), [data]);
  const [sizeKey, setSizeKey] = useState("32");
  const [a, setA] = useState<Product | null>(null);
  const [b, setB] = useState<Product | null>(null);
  const [remA, setRemA] = useState<Ingredient[]>([]);
  const [remB, setRemB] = useState<Ingredient[]>([]);
  const [noteA, setNoteA] = useState("");
  const [noteB, setNoteB] = useState("");
  const sizes = pizzas[0]?.sizes ?? [];
  const priceOf = (p: Product | null) => p?.sizes.find((s) => s.key === sizeKey)?.price ?? p?.price ?? 0;
  const price = Math.max(priceOf(a), priceOf(b));
  const toggle = (list: Ingredient[], set: (v: Ingredient[]) => void, ing: Ingredient) => set(list.some((x) => x.id === ing.id) ? list.filter((x) => x.id !== ing.id) : [...list, ing]);

  const add = () => {
    if (!a || !b) return;
    const size = a.sizes.find((s) => s.key === sizeKey) ?? a.sizes[0];
    cart.addItem({
      product_id: a.id, name: { fr: `${a.name.fr} / ${b.name.fr}`, de: `${a.name.de} / ${b.name.de}` }, image_url: a.image_url, unit_price: price, quantity: 1,
      size: { ...size, price }, options: [], removed_ingredients: remA, extras: [], note: noteA.trim(), is_alcohol: false,
      half: { product_id: b.id, name: b.name, removed_ingredients: remB, note: noteB.trim() },
    });
    toast.show(`${t("halfHalf")} – ${t("added")}`, "success");
    setA(null); setB(null); setRemA([]); setRemB([]); setNoteA(""); setNoteB("");
    onClose();
  };

  const half = (label: string, sel: Product | null, setSel: (p: Product | null) => void, rem: Ingredient[], setRem: (v: Ingredient[]) => void, note: string, setNote: (v: string) => void, tag: string) => (
    <View style={styles.box}>
      <Text style={styles.kicker}>{label}{sel ? ` · ${chf(priceOf(sel))}` : ""}</Text>
      <View style={styles.wrap}>
        {pizzas.map((p) => <Chip key={p.id} label={p.name.fr} selected={sel?.id === p.id} onPress={() => { setSel(p); setRem([]); }} testID={`half-${tag}-${p.id}`} />)}
      </View>
      {sel && sel.ingredients.length ? (
        <>
          <Text style={styles.hint}>{t("removeIngredients")}</Text>
          <View style={styles.wrap}>
            {sel.ingredients.map((ing) => <Chip key={ing.id} label={`– ${ing.fr}`} selected={rem.some((x) => x.id === ing.id)} onPress={() => toggle(rem, setRem, ing)} testID={`half-${tag}-rm-${ing.id}`} />)}
          </View>
        </>
      ) : null}
      {sel ? <Field label={t("kitchenNote")} value={note} onChangeText={setNote} testID={`half-${tag}-note`} /> : null}
    </View>
  );

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.screen}>
        <View style={styles.header}>
          <Text style={styles.title}>{t("halfHalf")}</Text>
          <Pressable onPress={onClose} style={styles.close} testID="half-close"><Feather name="x" size={22} color={colors.onSurface} /></Pressable>
        </View>
        <ScrollView contentContainerStyle={{ padding: 16, gap: 14, paddingBottom: 120 }} keyboardShouldPersistTaps="handled">
          <View style={styles.box}>
            <Text style={styles.kicker}>{t("size")}</Text>
            <View style={styles.wrap}>{sizes.map((s) => <Chip key={s.key} label={s.label} selected={sizeKey === s.key} onPress={() => setSizeKey(s.key)} testID={`half-size-${s.key}`} />)}</View>
          </View>
          {half(t("firstHalf"), a, setA, remA, setRemA, noteA, setNoteA, "a")}
          {half(t("secondHalf"), b, setB, remB, setRemB, noteB, setNoteB, "b")}
          <Text style={styles.hint}>{t("halfPriceRule")}</Text>
        </ScrollView>
        <View style={styles.cta}>
          <Button title={`${t("addToCart")} · ${chf(price)}`} size="xl" icon="plus" disabled={!a || !b} onPress={add} testID="half-add" />
        </View>
      </View>
    </Modal>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: 16, paddingTop: 24, borderBottomWidth: 1, borderBottomColor: colors.border },
  title: { fontFamily: FONT_DISPLAY, fontSize: 24, color: colors.onSurface },
  close: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  box: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10 },
  kicker: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "800", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8 },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  hint: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  cta: { position: "absolute", left: 0, right: 0, bottom: 0, padding: 16, paddingBottom: 28, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
}));
