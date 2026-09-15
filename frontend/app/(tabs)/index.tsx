import React, { useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, SectionList, Text, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import Animated, { FadeInDown } from "react-native-reanimated";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu } from "@/src/api";
import { useCart } from "@/src/cart";
import { ProductCard } from "@/src/components/product-card";
import { Button, FONT_DISPLAY, FONT_TEXT } from "@/src/components/ui";
import type { OrderType, Product } from "@/src/types";

const HERO = "https://images.unsplash.com/photo-1579751626657-72bc17010498?w=1400&q=85";

export function LanguageToggle({ inverse }: { inverse?: boolean }) {
  const { lang, setLang } = useI18n();
  const styles = useStyles();
  return (
    <View style={[styles.langWrap, inverse && styles.langWrapInverse]} testID="language-selector">
      {(["fr", "de"] as const).map((l) => (
        <Pressable key={l} testID={`lang-${l}`} onPress={() => setLang(l)} style={[styles.langBtn, lang === l && styles.langBtnActive]}>
          <Text style={[styles.langText, inverse && { color: inverse ? styles.langTextInverse.color : undefined }, lang === l && styles.langTextActive]}>{l.toUpperCase()}</Text>
        </Pressable>
      ))}
    </View>
  );
}

/** Premium Pickup / Delivery selector (two large buttons) */
export function OrderTypeSelector({ compact }: { compact?: boolean }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const { orderType, setOrderType } = useCart();
  const { data } = useMenu();
  const s = data?.settings;
  const items: { key: OrderType; icon: React.ComponentProps<typeof Feather>["name"]; label: string; hint: string; enabled: boolean }[] = [
    { key: "pickup", icon: "shopping-bag", label: t("pickup"), hint: t("pickupHint"), enabled: s?.pickup_enabled !== false },
    { key: "delivery", icon: "truck", label: t("delivery"), hint: t("deliveryHint"), enabled: s?.delivery_enabled !== false },
  ];
  return (
    <View style={styles.typeRow} testID="order-type-selector">
      {items.map((it) => {
        const on = orderType === it.key;
        return (
          <Pressable
            key={it.key}
            testID={`home-order-type-${it.key}`}
            disabled={!it.enabled}
            onPress={() => { Haptics.selectionAsync().catch(() => {}); setOrderType(it.key); }}
            style={({ pressed }) => [styles.typeBtn, compact && { height: 56 }, on && styles.typeBtnOn, !it.enabled && { opacity: 0.4 }, pressed && { transform: [{ scale: 0.98 }] }]}
          >
            <View style={[styles.typeIcon, on && styles.typeIconOn]}>
              <Feather name={it.icon} size={18} color={on ? colors.onBrandPrimary : colors.onSurface} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.typeLabel, on && styles.typeLabelOn]}>{it.label.toUpperCase()}</Text>
              {!compact ? <Text style={[styles.typeHint, on && styles.typeHintOn]}>{it.hint}</Text> : null}
            </View>
            {on ? <Feather name="check-circle" size={18} color={colors.onSurfaceInverse} /> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

export default function MenuScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t, tx } = useI18n();
  const { data, isLoading, isError, refetch } = useMenu();
  const [cat, setCat] = useState<string>("all");
  const listRef = useRef<SectionList<Product>>(null);

  const sections = useMemo(() => {
    if (!data) return [];
    const cats = cat === "all" ? data.categories.filter((c) => !c.filter) : data.categories.filter((c) => c.id === cat);
    return cats
      .map((c) => ({
        id: c.id,
        title: tx(c.name),
        filter: c.filter ?? null,
        data: c.filter ? data.products.filter((p) => p.options.some((o) => o.key === c.filter)) : data.products.filter((p) => p.category_id === c.id),
      }))
      .filter((s) => s.data.length > 0);
  }, [data, cat, tx]);

  const selectCat = (id: string) => {
    Haptics.selectionAsync().catch(() => {});
    setCat(id);
    listRef.current?.getScrollResponder()?.scrollTo?.({ y: 0, animated: true });
  };
  const orderNow = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    const pizza = data?.categories.find((c) => c.slug === "pizza");
    if (pizza) selectCat(pizza.id);
    listRef.current?.scrollToLocation?.({ sectionIndex: 0, itemIndex: 0, viewOffset: 0, animated: true });
  };

  const settings = data?.settings;

  return (
    <View style={styles.screen}>
      {/* Sticky chrome: brand + language + compact category rail */}
      <View style={[styles.header, { paddingTop: insets.top + 6 }]}>
        <View style={styles.headerRow}>
          <View style={styles.brandRow}>
            <View style={styles.logoDot}><Text style={styles.logoText}>H</Text></View>
            <Text style={styles.brand} testID="home-title">Hallo Magic Pizza</Text>
          </View>
          <LanguageToggle />
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips} style={styles.chipRow}>
          <CatChip label={t("all")} selected={cat === "all"} onPress={() => selectCat("all")} testID="category-chip-all" />
          {data?.categories.map((c) => (
            <CatChip key={c.id} label={tx(c.name)} selected={cat === c.id} onPress={() => selectCat(c.id)} testID={`category-chip-${c.slug}`} />
          ))}
        </ScrollView>
      </View>

      {isLoading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brandPrimary} size="large" /></View>
      ) : isError || !data ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>{t("loadError")}</Text>
          <Button title={t("retry")} onPress={() => refetch()} variant="outline" testID="menu-retry-button" />
        </View>
      ) : (
        <SectionList
          ref={listRef}
          sections={sections}
          keyExtractor={(p) => p.id}
          stickySectionHeadersEnabled={false}
          contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 24 }}
          ListHeaderComponent={
            cat === "all" ? (
              <Animated.View entering={FadeInDown.duration(500)}>
                <View style={styles.hero}>
                  <Image source={{ uri: HERO }} style={styles.heroImg} contentFit="cover" transition={400} />
                  <LinearGradient colors={[colors.scrimTransparent, colors.scrim]} start={{ x: 0.5, y: 0.15 }} end={{ x: 0.5, y: 1 }} style={styles.heroScrim} />
                  <View style={styles.heroText}>
                    <Text style={styles.heroKicker}>PIZZERIA · FRIBOURG</Text>
                    <Text style={styles.heroTitle}>{t("heroTitle")}</Text>
                    <Text style={styles.heroSub}>{t("heroSub")}</Text>
                    <Pressable testID="hero-order-now" onPress={orderNow} style={({ pressed }) => [styles.heroCta, pressed && { transform: [{ scale: 0.98 }], opacity: 0.9 }]}>
                      <Text style={styles.heroCtaText}>{t("orderNowCta")}</Text>
                      <Feather name="arrow-right" size={18} color={colors.onBrandPrimary} />
                    </Pressable>
                  </View>
                  {settings?.temporarily_closed ? (
                    <View style={styles.closedBanner} testID="closed-banner">
                      <Feather name="alert-circle" size={16} color={colors.onError} />
                      <Text style={styles.closedText}>{t("closedNow")}</Text>
                    </View>
                  ) : null}
                </View>
                <Text style={styles.howTo}>{t("howToGet")}</Text>
                <OrderTypeSelector />
              </Animated.View>
            ) : (
              <View style={{ marginTop: 8 }}><OrderTypeSelector compact /></View>
            )
          }
          renderSectionHeader={({ section }) => (
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle} testID={`section-${section.id}`}>{section.title}</Text>
              <View style={styles.sectionLine} />
            </View>
          )}
          renderItem={({ item, index, section }) => (
            <ProductCard product={item} index={index} onPress={() => router.push({ pathname: "/product/[id]", params: section.filter ? { id: item.id, option: section.filter } : { id: item.id } })} />
          )}
        />
      )}
    </View>
  );
}

function CatChip({ label, selected, onPress, testID }: { label: string; selected: boolean; onPress: () => void; testID: string }) {
  const styles = useStyles();
  return (
    <Pressable testID={testID} onPress={onPress} style={[styles.chip, selected && styles.chipOn]}>
      <Text style={[styles.chipText, selected && styles.chipTextOn]} numberOfLines={1}>{label}</Text>
    </Pressable>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  header: { backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 16, paddingBottom: 4, height: 52 },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  logoDot: { width: 34, height: 34, borderRadius: 17, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" },
  logoText: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onBrandPrimary },
  brand: { fontFamily: FONT_DISPLAY, fontSize: 21, color: colors.onSurface },
  langWrap: { flexDirection: "row", backgroundColor: colors.surfaceTertiary, borderRadius: 999, padding: 3 },
  langWrapInverse: { backgroundColor: colors.overlay },
  langBtn: { paddingHorizontal: 12, height: 30, borderRadius: 999, justifyContent: "center" },
  langBtnActive: { backgroundColor: colors.surfaceInverse },
  langText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "800", color: colors.muted },
  langTextInverse: { color: colors.onSurfaceInverse },
  langTextActive: { color: colors.onSurfaceInverse },
  chipRow: { height: 52 },
  chips: { gap: 8, paddingHorizontal: 16, alignItems: "center" },
  chip: { height: 34, paddingHorizontal: 14, borderRadius: 999, backgroundColor: colors.surfaceTertiary, justifyContent: "center", flexShrink: 0 },
  chipOn: { backgroundColor: colors.brandPrimary },
  chipText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.onSurfaceTertiary },
  chipTextOn: { color: colors.onBrandPrimary },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 16, padding: 24 },
  errorText: { fontFamily: FONT_TEXT, color: colors.muted, fontSize: 16 },
  hero: { height: 420, borderRadius: 28, overflow: "hidden", marginTop: 16, backgroundColor: colors.surfaceTertiary, shadowColor: colors.surfaceInverse, shadowOpacity: 0.18, shadowRadius: 20, shadowOffset: { width: 0, height: 10 }, elevation: 6 },
  heroImg: { width: "100%", height: "100%" },
  heroScrim: { position: "absolute", left: 0, right: 0, top: 0, bottom: 0 },
  heroText: { position: "absolute", left: 22, right: 22, bottom: 22, gap: 10 },
  heroKicker: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "800", letterSpacing: 2.5, color: colors.onSurfaceInverse, opacity: 0.85 },
  heroTitle: { fontFamily: FONT_DISPLAY, fontSize: 34, color: colors.onSurfaceInverse, lineHeight: 40 },
  heroSub: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceInverse, opacity: 0.9, lineHeight: 20 },
  heroCta: { marginTop: 6, alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: colors.brandPrimary, height: 54, paddingHorizontal: 24, borderRadius: 999 },
  heroCtaText: { fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "800", color: colors.onBrandPrimary, letterSpacing: 0.3 },
  closedBanner: { position: "absolute", top: 14, left: 14, right: 14, backgroundColor: colors.error, borderRadius: 12, padding: 10, flexDirection: "row", gap: 8, alignItems: "center" },
  closedText: { fontFamily: FONT_TEXT, color: colors.onError, fontWeight: "700" },
  howTo: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.muted, marginTop: 24, marginBottom: 10, letterSpacing: 0.3, textTransform: "uppercase" },
  typeRow: { flexDirection: "row", gap: 10 },
  typeBtn: { flex: 1, height: 72, borderRadius: 18, backgroundColor: colors.surfaceSecondary, borderWidth: 1.5, borderColor: colors.border, flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12 },
  typeBtnOn: { backgroundColor: colors.surfaceInverse, borderColor: colors.surfaceInverse },
  typeIcon: { width: 38, height: 38, borderRadius: 19, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  typeIconOn: { backgroundColor: colors.brandPrimary },
  typeLabel: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "800", letterSpacing: 0.8, color: colors.onSurface },
  typeLabelOn: { color: colors.onSurfaceInverse },
  typeHint: { fontFamily: FONT_TEXT, fontSize: 11, color: colors.muted, marginTop: 2 },
  typeHintOn: { color: colors.onSurfaceInverse, opacity: 0.8 },
  sectionHead: { flexDirection: "row", alignItems: "center", gap: 14, marginTop: 30, marginBottom: 16 },
  sectionTitle: { fontFamily: FONT_DISPLAY, fontSize: 28, color: colors.onSurface },
  sectionLine: { flex: 1, height: 1, backgroundColor: colors.borderStrong },
}));
