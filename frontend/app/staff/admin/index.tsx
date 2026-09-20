import React, { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Switch, Text, View } from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { imgUri, useMenu, useSaveProduct } from "@/src/api";
import { chf } from "@/src/format";
import { Badge, Button, Chip, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";

export default function AdminScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t, tx } = useI18n();
  const toast = useToast();
  const { data, isLoading } = useMenu(5000);
  const save = useSaveProduct();
  const [cat, setCat] = useState<string>("all");

  const cats = (data?.categories ?? []).filter((c) => !c.filter);
  const catIndex = new Map(cats.map((c, i) => [c.id, i]));
  // "all" view: grouped by category (categories order), inside a category: server order (Pizza du mois first, then manual ▲▼ order)
  const products = cat === "all"
    ? [...(data?.products ?? [])].sort((a, b) => (catIndex.get(a.category_id) ?? 99) - (catIndex.get(b.category_id) ?? 99))
    : (data?.products ?? []).filter((p) => p.category_id === cat);
  // Manual ordering (▲▼) is only offered inside one category; the Pizza du mois is always listed first automatically
  const movable = cat === "all" ? [] : products.filter((p) => p.highlight !== "moment");
  const move = (id: string, dir: -1 | 1) => {
    if (save.isPending) return;
    const i = movable.findIndex((p) => p.id === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= movable.length) return;
    // swap positions, then re-number sort 1..n inside the category so the order is always unambiguous
    const order = movable.map((p) => p.id); order[i] = movable[j].id; order[j] = movable[i].id;
    Promise.all(order.map((pid, idx) => { const p = movable.find((x) => x.id === pid)!; return p.sort === idx + 1 ? null : save.mutateAsync({ id: p.id, body: { sort: idx + 1 } }); }))
      .then(() => toast.show(t("saved"), "success"))
      .catch((e: any) => toast.show(e.message, "error"));
  };

  const toggle = async (id: string, available: boolean) => {
    try {
      await save.mutateAsync({ id, body: { available } });
      toast.show(available ? t("availableSwitch") : t("soldOutSwitch"), available ? "success" : "info");
    } catch (e: any) {
      toast.show(e.message, "error");
    }
  };

  return (
    <View style={styles.screen}>
      <ScreenHeader
        title={t("admin")}
        subtitle={`${data?.products.length ?? 0} ${t("products").toLowerCase()}`}
        testID="admin-title"
        right={
          <View style={{ flexDirection: "row", gap: 8 }}>
            <Pressable testID="admin-go-categories" onPress={() => router.push("/staff/admin/categories")} style={styles.iconBtn}><Feather name="list" size={20} color={colors.onSurface} /></Pressable>
            <Pressable testID="admin-go-extras" onPress={() => router.push("/staff/admin/extras")} style={styles.iconBtn}><Feather name="plus-square" size={20} color={colors.onSurface} /></Pressable>
            <Pressable testID="admin-go-security" onPress={() => router.push("/staff/admin/security")} style={styles.iconBtn}><Feather name="key" size={20} color={colors.onSurface} /></Pressable>
            <Pressable testID="admin-go-settings" onPress={() => router.push("/staff/admin/settings")} style={styles.iconBtn}><Feather name="sliders" size={20} color={colors.onSurface} /></Pressable>
          </View>
        }
      />
      <View style={styles.chipRow}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
          <Chip label={t("all")} selected={cat === "all"} onPress={() => setCat("all")} testID="admin-cat-all" />
          {cats.map((c) => <Chip key={c.id} label={tx(c.name)} selected={cat === c.id} onPress={() => setCat(c.id)} testID={`admin-cat-${c.slug}`} />)}
        </ScrollView>
      </View>
      {isLoading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brandPrimary} /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, gap: 10, paddingBottom: insets.bottom + 100 }}>
          {cat === "all" ? <Text style={styles.hint} testID="admin-reorder-hint">{t("reorderHint")}</Text> : null}
          {products.map((p) => {
            const pos = movable.findIndex((x) => x.id === p.id);
            return (
            <Pressable key={p.id} testID={`admin-product-${p.id}`} onPress={() => router.push({ pathname: "/staff/admin/product/[id]", params: { id: p.id } })} style={[styles.row, !p.available && { opacity: 0.6 }]}>
              {cat !== "all" ? (
                p.highlight === "moment" ? (
                  <View style={styles.firstTag} testID={`admin-product-first-${p.id}`}><Feather name="star" size={14} color={colors.brandPrimary} /><Text style={styles.firstTagText}>1er</Text></View>
                ) : (
                  <View style={{ gap: 4 }}>
                    <Pressable testID={`admin-product-up-${p.id}`} disabled={pos <= 0} onPress={() => move(p.id, -1)} style={[styles.arrow, pos <= 0 && styles.arrowOff]}><Feather name="chevron-up" size={18} color={colors.onSurface} /></Pressable>
                    <Pressable testID={`admin-product-down-${p.id}`} disabled={pos >= movable.length - 1} onPress={() => move(p.id, 1)} style={[styles.arrow, pos >= movable.length - 1 && styles.arrowOff]}><Feather name="chevron-down" size={18} color={colors.onSurface} /></Pressable>
                  </View>
                )
              ) : null}
              <Image source={{ uri: imgUri(p.image_url) }} style={styles.thumb} contentFit="cover" />
              <View style={{ flex: 1 }}>
                <Text style={styles.name} numberOfLines={1}>{p.name.fr}</Text>
                <Text style={styles.sub} numberOfLines={1}>{cat !== "all" && pos >= 0 ? `#${pos + 1} · ` : ""}{p.name.de} · {p.sizes.length ? p.sizes.map((s) => `${s.label} ${s.price}` ).join(" / ") : chf(p.price)}</Text>
                <View style={{ flexDirection: "row", gap: 6, marginTop: 4 }}>
                  <Badge label={p.available ? t("availableSwitch") : t("soldOutSwitch")} tone={p.available ? "success" : "error"} testID={`admin-availability-${p.id}`} />
                  <Badge label={`${t("vat")} ${(p.vat_rate ?? (p.is_alcohol ? data?.settings.vat_rate_alcohol : data?.settings.vat_rate_standard) ?? 0).toFixed(1)}%`} tone="neutral" testID={`admin-vat-${p.id}`} />
                  {p.highlight === "moment" ? <Badge label={`${t("highlightMoment")} · ${t("alwaysFirst")}`} tone="warning" /> : null}
                  {p.is_alcohol ? <Badge label="18+" tone="warning" /> : null}
                  {p.customizable ? <Badge label={t("customize")} tone="neutral" /> : null}
                </View>
              </View>
              <Switch testID={`admin-toggle-${p.id}`} value={p.available} onValueChange={(v) => toggle(p.id, v)} trackColor={{ true: colors.success, false: colors.borderStrong }} thumbColor={colors.surfaceSecondary} />
            </Pressable>
            );
          })}
        </ScrollView>
      )}
      <View style={[styles.fab, { bottom: insets.bottom + 16 }]}>
        <Button title={t("newProduct")} icon="plus" size="lg" onPress={() => router.push({ pathname: "/staff/admin/product/[id]", params: { id: "new" } })} testID="admin-new-product" />
      </View>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  chipRow: { height: 56, justifyContent: "center", borderBottomWidth: 1, borderBottomColor: colors.border },
  chips: { gap: 8, paddingHorizontal: 16, alignItems: "center" },
  row: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.surfaceSecondary, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 10 },
  arrow: { width: 36, height: 30, borderRadius: 8, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  arrowOff: { opacity: 0.3 },
  firstTag: { width: 36, height: 64, borderRadius: 8, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center", gap: 2 },
  firstTagText: { fontFamily: FONT_DISPLAY, fontSize: 11, color: colors.brandPrimary },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, textAlign: "center", paddingVertical: 4 },
  thumb: { width: 56, height: 56, borderRadius: 10, backgroundColor: colors.surfaceTertiary },
  name: { fontFamily: FONT_DISPLAY, fontSize: 17, color: colors.onSurface },
  sub: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, marginTop: 2 },
  fab: { position: "absolute", left: 16, right: 16 },
}));
