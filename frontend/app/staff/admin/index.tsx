import React, { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Switch, Text, View } from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu, useSaveProduct } from "@/src/api";
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
  const products = (data?.products ?? []).filter((p) => cat === "all" || p.category_id === cat);

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
            <Pressable testID="admin-go-extras" onPress={() => router.push("/staff/admin/extras")} style={styles.iconBtn}><Feather name="plus-square" size={20} color={colors.onSurface} /></Pressable>
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
          {products.map((p) => (
            <Pressable key={p.id} testID={`admin-product-${p.id}`} onPress={() => router.push({ pathname: "/staff/admin/product/[id]", params: { id: p.id } })} style={[styles.row, !p.available && { opacity: 0.6 }]}>
              <Image source={{ uri: p.image_url || undefined }} style={styles.thumb} contentFit="cover" />
              <View style={{ flex: 1 }}>
                <Text style={styles.name} numberOfLines={1}>{p.name.fr}</Text>
                <Text style={styles.sub} numberOfLines={1}>{p.name.de} · {p.sizes.length ? p.sizes.map((s) => `${s.label} ${s.price}` ).join(" / ") : chf(p.price)}</Text>
                <View style={{ flexDirection: "row", gap: 6, marginTop: 4 }}>
                  <Badge label={p.available ? t("availableSwitch") : t("soldOutSwitch")} tone={p.available ? "success" : "error"} testID={`admin-availability-${p.id}`} />
                  {p.customizable ? <Badge label={t("customize")} tone="neutral" /> : null}
                </View>
              </View>
              <Switch testID={`admin-toggle-${p.id}`} value={p.available} onValueChange={(v) => toggle(p.id, v)} trackColor={{ true: colors.success, false: colors.borderStrong }} thumbColor={colors.surfaceSecondary} />
            </Pressable>
          ))}
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
  thumb: { width: 56, height: 56, borderRadius: 10, backgroundColor: colors.surfaceTertiary },
  name: { fontFamily: FONT_DISPLAY, fontSize: 17, color: colors.onSurface },
  sub: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, marginTop: 2 },
  fab: { position: "absolute", left: 16, right: 16 },
}));
