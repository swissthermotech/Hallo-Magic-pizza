import React, { useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, SectionList, Text, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu } from "@/src/api";
import { ProductCard } from "@/src/components/product-card";
import { Button, Chip, FONT_DISPLAY, FONT_TEXT } from "@/src/components/ui";
import type { Product } from "@/src/types";

const HERO = "https://images.unsplash.com/photo-1579751626657-72bc17010498?w=1200&q=80";

export function LanguageToggle({ compact }: { compact?: boolean }) {
  const { lang, setLang } = useI18n();
  const styles = useStyles();
  return (
    <View style={styles.langWrap} testID="language-selector">
      {(["fr", "de"] as const).map((l) => (
        <Pressable key={l} testID={`lang-${l}`} onPress={() => setLang(l)} style={[styles.langBtn, lang === l && styles.langBtnActive, compact && { paddingHorizontal: 10 }]}>
          <Text style={[styles.langText, lang === l && styles.langTextActive]}>{l.toUpperCase()}</Text>
        </Pressable>
      ))}
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
        data: c.filter
          ? data.products.filter((p) => p.options.some((o) => o.key === c.filter))
          : data.products.filter((p) => p.category_id === c.id),
      }))
      .filter((s) => s.data.length > 0);
  }, [data, cat, tx]);

  const selectCat = (id: string) => {
    Haptics.selectionAsync().catch(() => {});
    setCat(id);
    listRef.current?.getScrollResponder()?.scrollTo?.({ y: 0, animated: true });
  };

  const settings = data?.settings;

  return (
    <View style={styles.screen}>
      {/* Sticky chrome */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.brand} testID="home-title">Hallo Magic Pizza</Text>
            <Text style={styles.tagline}>{t("heroTagline")}</Text>
          </View>
          <LanguageToggle />
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips} style={styles.chipRow}>
          <Chip label={t("all")} selected={cat === "all"} onPress={() => selectCat("all")} testID="category-chip-all" />
          {data?.categories.map((c) => (
            <Chip key={c.id} label={tx(c.name)} selected={cat === c.id} onPress={() => selectCat(c.id)} testID={`category-chip-${c.slug}`} />
          ))}
        </ScrollView>
      </View>

      {isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brandPrimary} size="large" />
        </View>
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
            <View style={styles.hero}>
              <Image source={{ uri: HERO }} style={styles.heroImg} contentFit="cover" />
              <LinearGradient colors={[colors.scrimTransparent, colors.scrim]} style={styles.heroScrim} />
              <View style={styles.heroText}>
                <Text style={styles.heroTitle}>Pizza al forno,{"\n"}come in Italia.</Text>
                <View style={styles.heroBadges}>
                  {settings?.pickup_enabled ? <HeroBadge icon="shopping-bag" label={t("pickup")} /> : null}
                  {settings?.delivery_enabled ? <HeroBadge icon="truck" label={t("delivery")} /> : null}
                </View>
              </View>
              {settings?.temporarily_closed ? (
                <View style={styles.closedBanner} testID="closed-banner">
                  <Feather name="alert-circle" size={16} color={colors.onError} />
                  <Text style={styles.closedText}>{t("closedNow")}</Text>
                </View>
              ) : null}
            </View>
          }
          renderSectionHeader={({ section }) => (
            <Text style={styles.sectionTitle} testID={`section-${section.id}`}>{section.title}</Text>
          )}
          renderItem={({ item, index, section }) => (
            <ProductCard product={item} index={index} onPress={() => router.push({ pathname: "/product/[id]", params: section.filter ? { id: item.id, option: section.filter } : { id: item.id } })} />
          )}
        />
      )}
    </View>
  );
}

function HeroBadge({ icon, label }: { icon: React.ComponentProps<typeof Feather>["name"]; label: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.heroBadge}>
      <Feather name={icon} size={13} color={colors.onSurfaceInverse} />
      <Text style={styles.heroBadgeText}>{label}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  header: { backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 16, paddingBottom: 6 },
  brand: { fontFamily: FONT_DISPLAY, fontSize: 24, color: colors.onSurface },
  tagline: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, marginTop: 1 },
  langWrap: { flexDirection: "row", backgroundColor: colors.surfaceTertiary, borderRadius: 999, padding: 3 },
  langBtn: { paddingHorizontal: 12, height: 32, borderRadius: 999, justifyContent: "center" },
  langBtnActive: { backgroundColor: colors.surfaceInverse },
  langText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.muted },
  langTextActive: { color: colors.onSurfaceInverse },
  chipRow: { height: 56 },
  chips: { gap: 8, paddingHorizontal: 16, alignItems: "center" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 16, padding: 24 },
  errorText: { fontFamily: FONT_TEXT, color: colors.muted, fontSize: 16 },
  hero: { height: 200, borderRadius: 20, overflow: "hidden", marginTop: 16, marginBottom: 8, backgroundColor: colors.surfaceTertiary },
  heroImg: { width: "100%", height: "100%" },
  heroScrim: { position: "absolute", left: 0, right: 0, top: 0, bottom: 0 },
  heroText: { position: "absolute", left: 18, right: 18, bottom: 16, gap: 10 },
  heroTitle: { fontFamily: FONT_DISPLAY, fontSize: 28, color: colors.onSurfaceInverse, lineHeight: 34 },
  heroBadges: { flexDirection: "row", gap: 8 },
  heroBadge: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: colors.overlay, borderRadius: 999, paddingHorizontal: 10, height: 28 },
  heroBadgeText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "700", color: colors.onSurfaceInverse },
  closedBanner: { position: "absolute", top: 12, left: 12, right: 12, backgroundColor: colors.error, borderRadius: 10, padding: 10, flexDirection: "row", gap: 8, alignItems: "center" },
  closedText: { fontFamily: FONT_TEXT, color: colors.onError, fontWeight: "700" },
  sectionTitle: { fontFamily: FONT_DISPLAY, fontSize: 24, color: colors.onSurface, marginTop: 20, marginBottom: 12 },
}));
