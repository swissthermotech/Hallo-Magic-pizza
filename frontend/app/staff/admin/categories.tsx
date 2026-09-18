import React, { useState } from "react";
import { Pressable, Switch, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useDeleteCategory, useMenu, useSaveCategory } from "@/src/api";
import { Button, Field, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";
import type { Category } from "@/src/types";

/** Admin: categories – FR/DE names, order (▲▼), active/inactive, create. Products keep their category_id. */
export default function CategoriesScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const toast = useToast();
  const { data } = useMenu(0);
  const save = useSaveCategory();
  const del = useDeleteCategory();
  const [edit, setEdit] = useState<Partial<Category> | null>(null);
  const cats = [...(data?.categories ?? [])].sort((a, b) => a.sort - b.sort);
  const body = (c: Category, patch: Partial<Category>): Omit<Category, "id"> => ({ slug: c.slug, name: c.name, sort: c.sort, image_url: c.image_url ?? null, active: c.active, filter: c.filter ?? null, ...patch });
  const persist = (id: string | undefined, b: Omit<Category, "id">) => save.mutateAsync({ id, body: b }).catch((e) => toast.show(e.message, "error"));
  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= cats.length) return;
    const a = cats[i], b = cats[j];
    // swap positions (sort values re-numbered 1..n so ordering is always unambiguous)
    const order = cats.map((c) => c.id); order[i] = b.id; order[j] = a.id;
    Promise.all(order.map((cid, idx) => { const c = cats.find((x) => x.id === cid)!; return c.sort === idx + 1 ? null : persist(c.id, body(c, { sort: idx + 1 })); })).then(() => toast.show(t("saved"), "success"));
  };
  const submit = async () => {
    if (!edit?.name?.fr) return toast.show(t("required"), "error");
    const slug = edit.slug || edit.name.fr.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    await persist(edit.id, { slug, name: { fr: edit.name.fr, de: edit.name.de || edit.name.fr }, sort: edit.sort ?? cats.length + 1, image_url: edit.image_url ?? null, active: edit.active ?? true, filter: edit.filter ?? null });
    toast.show(t("saved"), "success");
    setEdit(null);
  };
  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("categoriesAdmin")} subtitle={`${cats.length}`} testID="categories-title" right={<Pressable testID="category-new" onPress={() => setEdit({ name: { fr: "", de: "" }, active: true })} style={styles.iconBtn}><Feather name="plus" size={20} color={colors.onBrandPrimary} /></Pressable>} />
      <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, gap: 10, paddingBottom: insets.bottom + 24 }} bottomOffset={40}>
        {edit ? (
          <View style={styles.editor} testID="category-editor">
            <Field label={t("nameFr")} value={edit.name?.fr ?? ""} onChangeText={(v) => setEdit({ ...edit, name: { fr: v, de: edit.name?.de ?? "" } })} testID="category-name-fr" />
            <Field label={t("nameDe")} value={edit.name?.de ?? ""} onChangeText={(v) => setEdit({ ...edit, name: { fr: edit.name?.fr ?? "", de: v } })} testID="category-name-de" />
            <Field label={t("photoUrl")} value={edit.image_url ?? ""} onChangeText={(v) => setEdit({ ...edit, image_url: v })} autoCapitalize="none" testID="category-image" />
            <View style={{ flexDirection: "row", gap: 10 }}>
              <Button title={t("close")} variant="outline" onPress={() => setEdit(null)} style={{ flex: 1 }} testID="category-cancel" />
              <Button title={t("save")} loading={save.isPending} onPress={submit} style={{ flex: 2 }} testID="category-save" />
            </View>
            {edit.id && !(data?.products ?? []).some((p) => p.category_id === edit.id) ? <Button title={t("deleteCategory")} variant="outline" icon="trash-2" loading={del.isPending} onPress={() => del.mutateAsync(edit.id!).then(() => { toast.show(t("deleteCategory"), "info"); setEdit(null); }).catch((e) => toast.show(e.message, "error"))} testID="category-delete" /> : null}
          </View>
        ) : null}
        {cats.map((c, i) => (
          <View key={c.id} style={[styles.row, !c.active && { opacity: 0.55 }]} testID={`category-item-${c.slug}`}>
            <View style={{ gap: 4 }}>
              <Pressable testID={`category-up-${c.slug}`} onPress={() => move(i, -1)} style={styles.arrow}><Feather name="chevron-up" size={18} color={colors.onSurface} /></Pressable>
              <Pressable testID={`category-down-${c.slug}`} onPress={() => move(i, 1)} style={styles.arrow}><Feather name="chevron-down" size={18} color={colors.onSurface} /></Pressable>
            </View>
            <Pressable style={{ flex: 1 }} onPress={() => setEdit(c)} testID={`category-edit-${c.slug}`}>
              <Text style={styles.name}>{c.name.fr} <Text style={styles.de}>· {c.name.de}</Text></Text>
              <Text style={styles.sub}>#{i + 1} · {data?.products.filter((p) => p.category_id === c.id).length ?? 0} {t("products").toLowerCase()}</Text>
            </Pressable>
            <Switch testID={`category-toggle-${c.slug}`} value={c.active} onValueChange={(v) => { persist(c.id, body(c, { active: v })); }} trackColor={{ true: colors.success, false: colors.borderStrong }} thumbColor={colors.surfaceSecondary} />
          </View>
        ))}
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" },
  editor: { backgroundColor: colors.surfaceTertiary, borderRadius: 16, padding: 14, gap: 12 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.surfaceSecondary, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12 },
  arrow: { width: 36, height: 30, borderRadius: 8, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  name: { fontFamily: FONT_DISPLAY, fontSize: 17, color: colors.onSurface },
  de: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  sub: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, marginTop: 2 },
}));
