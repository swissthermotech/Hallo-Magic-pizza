import React, { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, Switch, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useDeleteProduct, useMenu, useSaveProduct } from "@/src/api";
import { Badge, Button, Chip, Field, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast, VatPicker } from "@/src/components/ui";
import { PhotoManager } from "@/src/components/photo-manager";
import type { AlcoholType, Product, ProductOption } from "@/src/types";

const DOUGH_TEMPLATE: ProductOption[] = [
  { key: "classic", group: "dough", name: { fr: "Pâte classique", de: "Klassischer Teig" }, price: 0, price_by_size: {}, only_sizes: [], default: true },
  { key: "gluten_free", group: "dough", name: { fr: "Pâte sans gluten", de: "Glutenfreier Teig" }, price: 4, price_by_size: {}, only_sizes: ["32"], default: false },
  { key: "lactose_free", group: "extra_option", name: { fr: "Sans lactose", de: "Laktosefrei" }, price: 4, price_by_size: { "32": 4, "40": 7, "50": 10 }, only_sizes: [], default: false },
];

export default function ProductEditor() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const isNew = id === "new";
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const toast = useToast();
  const { data } = useMenu(0);
  const save = useSaveProduct();
  const del = useDeleteProduct();
  const product = data?.products.find((p) => p.id === id);

  const [f, setF] = useState({ nameFr: "", nameDe: "", descFr: "", descDe: "", price: "", image: "", category: "", allergFr: "", allergDe: "", originFr: "", originDe: "", ingredients: "", sizes: "" });
  const [available, setAvailable] = useState(true);
  const [customizable, setCustomizable] = useState(false);
  const [isAlcohol, setIsAlcohol] = useState(false);
  const [alcoholType, setAlcoholType] = useState<AlcoholType>("fermented");
  const [extraPhotos, setExtraPhotos] = useState<string[]>([]);
  const [vatRate, setVatRate] = useState<number | null>(null);
  const [pizzaOptions, setPizzaOptions] = useState(false);
  const [allowed, setAllowed] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (loaded || !data) return;
    if (product) {
      setF({
        nameFr: product.name.fr, nameDe: product.name.de, descFr: product.description.fr, descDe: product.description.de,
        price: String(product.price), image: product.image_url || "", category: product.category_id,
        allergFr: product.allergens.fr, allergDe: product.allergens.de, originFr: product.origin?.fr ?? "", originDe: product.origin?.de ?? "",
        ingredients: product.ingredients.map((i) => `${i.fr} | ${i.de}`).join("\n"),
        sizes: product.sizes.map((s) => `${s.key} | ${s.label} | ${s.price}`).join("\n"),
      });
      setAvailable(product.available);
      setCustomizable(product.customizable);
      setIsAlcohol(product.is_alcohol);
      setAlcoholType(product.alcohol_type ?? "fermented");
      setExtraPhotos(product.images ?? []);
      setVatRate(product.vat_rate ?? null);
      setPizzaOptions(product.options.length > 0);
      setAllowed(product.allowed_extra_ids);
    } else if (isNew) {
      setF((p) => ({ ...p, category: data.categories.find((c) => !c.filter)?.id ?? "" }));
    }
    setLoaded(true);
  }, [data, product, isNew, loaded]);

  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));
  const extras = data?.extras ?? [];
  const allExtraKeys = extras.map((e) => e.key);

  const submit = async () => {
    const price = parseFloat(f.price.replace(",", "."));
    if (!f.nameFr.trim() || isNaN(price) || !f.category) {
      toast.show(t("required"), "error");
      return;
    }
    const ingredients = f.ingredients.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
      const [fr, de] = l.split("|").map((s) => s.trim());
      return { id: fr.toLowerCase().replace(/\s+/g, "_"), fr, de: de || fr };
    });
    const sizes = f.sizes.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
      const [key, label, p] = l.split("|").map((s) => s.trim());
      return { key, label: label || key, price: parseFloat((p || "0").replace(",", ".")) || 0 };
    });
    const body: Partial<Product> = {
      category_id: f.category,
      name: { fr: f.nameFr.trim(), de: f.nameDe.trim() || f.nameFr.trim() },
      description: { fr: f.descFr.trim(), de: f.descDe.trim() || f.descFr.trim() },
      price,
      image_url: f.image.trim() || null,
      images: extraPhotos,
      allergens: { fr: f.allergFr, de: f.allergDe },
      origin: { fr: f.originFr, de: f.originDe },
      ingredients,
      sizes,
      options: pizzaOptions ? (product?.options.length ? product.options : DOUGH_TEMPLATE) : [],
      customizable,
      allowed_extra_ids: customizable ? allowed : [],
      available,
      is_alcohol: isAlcohol,
      alcohol_type: isAlcohol ? alcoholType : null,
      vat_rate: vatRate ?? (isAlcohol ? data!.settings.vat_rate_alcohol : data!.settings.vat_rate_standard),
    };
    try {
      await save.mutateAsync({ id: isNew ? undefined : id, body });
      toast.show(t("saved"), "success");
      router.back();
    } catch (e: any) {
      toast.show(e.message, "error");
    }
  };

  const remove = async () => {
    try {
      await del.mutateAsync(id!);
      toast.show(t("deleteProduct"), "info");
      router.back();
    } catch (e: any) {
      toast.show(e.message, "error");
    }
  };

  if (!data || !loaded) {
    return <View style={[styles.screen, styles.center]}><ActivityIndicator color={colors.brandPrimary} /></View>;
  }

  return (
    <View style={styles.screen}>
      <ScreenHeader title={isNew ? t("newProduct") : f.nameFr || t("edit")} testID="product-editor-title" />
      <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, gap: 14, paddingBottom: insets.bottom + 120 }} bottomOffset={140}>
        <Text style={styles.section}>{t("photos")}</Text>
        <PhotoManager main={f.image || null} extra={extraPhotos} onChange={(m, ex) => { set("image")(m || ""); setExtraPhotos(ex); }} />
        <Field label={t("photoUrl")} value={f.image} onChangeText={set("image")} autoCapitalize="none" testID="editor-image" />

        <Text style={styles.section}>{t("category")}</Text>
        <View style={styles.wrap}>
          {data.categories.filter((c) => !c.filter).map((c) => <Chip key={c.id} label={c.name.fr} selected={f.category === c.id} onPress={() => set("category")(c.id)} testID={`editor-cat-${c.slug}`} />)}
        </View>

        <Text style={styles.section}>Français</Text>
        <Field label={t("nameFr")} value={f.nameFr} onChangeText={set("nameFr")} testID="editor-name-fr" />
        <Field label={t("descFr")} value={f.descFr} onChangeText={set("descFr")} multiline testID="editor-desc-fr" />
        <Text style={styles.section}>Deutsch</Text>
        <Field label={t("nameDe")} value={f.nameDe} onChangeText={set("nameDe")} testID="editor-name-de" />
        <Field label={t("descDe")} value={f.descDe} onChangeText={set("descDe")} multiline testID="editor-desc-de" />

        <Text style={styles.section}>{t("price")}</Text>
        <Field label={`${t("price")} (CHF)`} value={f.price} onChangeText={set("price")} keyboardType="decimal-pad" testID="editor-price" />
        <Field label={t("sizesList")} value={f.sizes} onChangeText={set("sizes")} multiline placeholder={"32 | 32cm | 18\n40 | 40cm | 31\n50 | 50cm | 40"} testID="editor-sizes" />

        <Text style={styles.section}>{t("ingredients")}</Text>
        <Field label={t("ingredientsList")} value={f.ingredients} onChangeText={set("ingredients")} multiline placeholder={"tomate | Tomaten\nmozzarella | Mozzarella"} testID="editor-ingredients" />
        <Field label={`${t("allergens")} (FR)`} value={f.allergFr} onChangeText={set("allergFr")} testID="editor-allergens-fr" />
        <Field label={`${t("origin")} (FR)`} value={f.originFr} onChangeText={set("originFr")} placeholder="ex. Jambon: Suisse" testID="editor-origin-fr" />
        <Field label={`${t("origin")} (DE)`} value={f.originDe} onChangeText={set("originDe")} testID="editor-origin-de" />
        <Field label={`${t("allergens")} (DE)`} value={f.allergDe} onChangeText={set("allergDe")} testID="editor-allergens-de" />

        <SwitchRow label={t("availableSwitch")} value={available} onChange={setAvailable} testID="editor-available" />
        <SwitchRow label={t("customize")} value={customizable} onChange={setCustomizable} testID="editor-customizable" />
        <SwitchRow label={`${t("dough")} / ${t("options")} (pizza)`} value={pizzaOptions} onChange={setPizzaOptions} testID="editor-pizza-options" />
        <SwitchRow label={t("alcoholProduct")} value={isAlcohol} onChange={(v) => { setIsAlcohol(v); if (vatRate === null || vatRate === (v ? data.settings.vat_rate_standard : data.settings.vat_rate_alcohol)) setVatRate(v ? data.settings.vat_rate_alcohol : data.settings.vat_rate_standard); }} testID="editor-alcohol" />
        {isAlcohol ? (
          <View style={{ gap: 8 }}>
            <Text style={styles.switchLabel}>{t("alcoholType")}</Text>
            <Chip label={t("alcoholFermented")} selected={alcoholType === "fermented"} onPress={() => setAlcoholType("fermented")} testID="editor-alcohol-fermented" />
            <Chip label={t("alcoholSpirits")} selected={alcoholType === "spirits"} onPress={() => setAlcoholType("spirits")} testID="editor-alcohol-spirits" />
            <Badge label={`${alcoholType === "spirits" ? 18 : 16}+ · ALCOOL`} tone="warning" testID="editor-alcohol-badge" />
          </View>
        ) : null}

        <Text style={styles.section}>{t("vat")}</Text>
        <VatPicker label={`${t("vatRate")} (${t("vatIncluded").toLowerCase()})`} value={vatRate ?? (isAlcohol ? data.settings.vat_rate_alcohol : data.settings.vat_rate_standard)} onChange={setVatRate} testID="editor-vat" />

        {customizable ? (
          <>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={styles.section}>{t("allowedExtras")} ({allowed.length})</Text>
              <Pressable testID="editor-extras-all" onPress={() => setAllowed(allowed.length === allExtraKeys.length ? [] : allExtraKeys)}><Text style={styles.link}>{allowed.length === allExtraKeys.length ? "—" : t("all")}</Text></Pressable>
            </View>
            <View style={styles.wrap}>
              {extras.map((e) => (
                <Chip key={e.id} label={`${e.name.fr} +${e.price}`} selected={allowed.includes(e.key) || allowed.includes(e.id)} onPress={() => setAllowed((p) => (p.includes(e.key) ? p.filter((k) => k !== e.key && k !== e.id) : [...p.filter((k) => k !== e.id), e.key]))} testID={`editor-extra-${e.key}`} />
              ))}
            </View>
          </>
        ) : null}

        {!isNew ? <Button title={t("deleteProduct")} variant="outline" icon="trash-2" onPress={remove} loading={del.isPending} testID="editor-delete" style={{ marginTop: 12 }} /> : null}
      </KeyboardAwareScrollView>
      <View style={[styles.cta, { paddingBottom: insets.bottom + 12 }]}>
        <Button title={t("save")} size="lg" icon="check" loading={save.isPending} onPress={submit} testID="editor-save" />
      </View>
    </View>
  );
}

function SwitchRow({ label, value, onChange, testID }: { label: string; value: boolean; onChange: (v: boolean) => void; testID: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.switchRow}>
      <Text style={styles.switchLabel}>{label}</Text>
      <Switch testID={testID} value={value} onValueChange={onChange} trackColor={{ true: colors.success, false: colors.borderStrong }} thumbColor={colors.surfaceSecondary} />
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  center: { alignItems: "center", justifyContent: "center" },
  section: { fontFamily: FONT_DISPLAY, fontSize: 19, color: colors.onSurface, marginTop: 6 },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  link: { fontFamily: FONT_TEXT, color: colors.brandPrimary, fontWeight: "700" },
  switchRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", backgroundColor: colors.surfaceSecondary, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14, height: 52 },
  switchLabel: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "600", color: colors.onSurface },
  cta: { position: "absolute", left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 12, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
}));
