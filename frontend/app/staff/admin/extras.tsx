import React, { useState } from "react";
import { Pressable, Switch, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useDeleteExtra, useMenu, useSaveExtra } from "@/src/api";
import { chf } from "@/src/format";
import { Button, Field, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast, VatPicker } from "@/src/components/ui";
import type { Extra } from "@/src/types";

export default function ExtrasScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const toast = useToast();
  const { data } = useMenu(0);
  const save = useSaveExtra();
  const del = useDeleteExtra();
  const [edit, setEdit] = useState<Partial<Extra> | null>(null);

  // Per-size supplement prices (32 / 40 / 50 cm) – empty field = use the default price
  const SIZES = ["32", "40", "50"];
  const pbs = (m?: Record<string, number> | null) => Object.fromEntries(Object.entries(m ?? {}).filter(([, v]) => v !== undefined && v !== null && !Number.isNaN(v)));
  const submit = async () => {
    if (!edit?.name?.fr || edit.price === undefined) return toast.show(t("required"), "error");
    const key = edit.key || edit.name.fr.toLowerCase().replace(/[^a-z0-9]+/g, "_");
    try {
      await save.mutateAsync({ id: edit.id, body: { key, name: { fr: edit.name.fr, de: edit.name.de || edit.name.fr }, price: Number(edit.price) || 0, price_by_size: pbs(edit.price_by_size), available: edit.available ?? true, max_quantity: edit.max_quantity ?? 1, vat_rate: edit.vat_rate ?? data?.settings.vat_rate_standard ?? 2.6 } });
      toast.show(t("saved"), "success");
      setEdit(null);
    } catch (e: any) {
      toast.show(e.message, "error");
    }
  };

  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("extrasAdmin")} subtitle={`${data?.extras.length ?? 0}`} testID="extras-title" right={<Pressable testID="extras-new" onPress={() => setEdit({ name: { fr: "", de: "" }, price: 2, available: true, max_quantity: 1 })} style={styles.iconBtn}><Feather name="plus" size={20} color={colors.onBrandPrimary} /></Pressable>} />
      <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, gap: 10, paddingBottom: insets.bottom + 24 }} bottomOffset={40}>
        {edit ? (
          <View style={styles.editor} testID="extra-editor">
            <Field label={t("nameFr")} value={edit.name?.fr ?? ""} onChangeText={(v) => setEdit({ ...edit, name: { fr: v, de: edit.name?.de ?? "" } })} testID="extra-name-fr" />
            <Field label={t("nameDe")} value={edit.name?.de ?? ""} onChangeText={(v) => setEdit({ ...edit, name: { fr: edit.name?.fr ?? "", de: v } })} testID="extra-name-de" />
            <View style={{ flexDirection: "row", gap: 10 }}>
              <Field label={`${t("price")} (CHF)`} value={String(edit.price ?? "")} onChangeText={(v) => setEdit({ ...edit, price: parseFloat(v.replace(",", ".")) || 0 })} keyboardType="decimal-pad" style={{ flex: 1 }} testID="extra-price" />
              <Field label="Max" value={String(edit.max_quantity ?? 1)} onChangeText={(v) => setEdit({ ...edit, max_quantity: parseInt(v, 10) || 1 })} keyboardType="number-pad" style={{ flex: 1 }} testID="extra-max" />
            </View>
            <Text style={styles.sub}>{t("pricePerSize")}</Text>
            <View style={{ flexDirection: "row", gap: 10 }}>
              {SIZES.map((k) => (
                <Field key={k} label={`${k} cm`} value={edit.price_by_size?.[k] !== undefined ? String(edit.price_by_size[k]) : ""} placeholder={String(edit.price ?? "")}
                  onChangeText={(v) => { const m = { ...(edit.price_by_size ?? {}) }; const n = parseFloat(v.replace(",", ".")); if (v.trim() === "" || Number.isNaN(n)) delete m[k]; else m[k] = n; setEdit({ ...edit, price_by_size: m }); }}
                  keyboardType="decimal-pad" style={{ flex: 1 }} testID={`extra-price-${k}`} />
              ))}
            </View>
            <VatPicker label={t("vatRate")} value={edit.vat_rate ?? data?.settings.vat_rate_standard} onChange={(v) => setEdit({ ...edit, vat_rate: v })} testID="extra-vat" />
            <View style={{ flexDirection: "row", gap: 10 }}>
              <Button title={t("close")} variant="outline" onPress={() => setEdit(null)} style={{ flex: 1 }} testID="extra-cancel" />
              <Button title={t("save")} loading={save.isPending} onPress={submit} style={{ flex: 2 }} testID="extra-save" />
            </View>
            {edit.id ? <Button title={t("deleteExtra")} variant="outline" icon="trash-2" loading={del.isPending} onPress={() => del.mutateAsync(edit.id!).then(() => { toast.show(t("deleteExtra"), "info"); setEdit(null); }).catch((e) => toast.show(e.message, "error"))} testID="extra-delete" /> : null}
          </View>
        ) : null}
        {(data?.extras ?? []).map((e) => (
          <Pressable key={e.id} testID={`extra-item-${e.key}`} onPress={() => setEdit(e)} style={[styles.row, !e.available && { opacity: 0.55 }]}>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{e.name.fr} <Text style={styles.de}>· {e.name.de}</Text></Text>
              <Text style={styles.sub}>{e.price_by_size && Object.keys(e.price_by_size).length ? SIZES.map((k) => `${k}: ${chf(e.price_by_size?.[k] ?? e.price)}`).join(" · ") : chf(e.price)} · max {e.max_quantity} · {t("vat")} {(e.vat_rate ?? data?.settings.vat_rate_standard ?? 0).toFixed(1)}%</Text>
            </View>
            <Switch testID={`extra-toggle-${e.key}`} value={e.available} onValueChange={(v) => { save.mutateAsync({ id: e.id, body: { key: e.key, name: e.name, price: e.price, price_by_size: e.price_by_size ?? {}, available: v, max_quantity: e.max_quantity, vat_rate: e.vat_rate ?? null } }).catch((err) => toast.show(err.message, "error")); }} trackColor={{ true: colors.success, false: colors.borderStrong }} thumbColor={colors.surfaceSecondary} />
          </Pressable>
        ))}
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" },
  editor: { backgroundColor: colors.surfaceTertiary, borderRadius: 16, padding: 14, gap: 12 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.surfaceSecondary, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 14 },
  name: { fontFamily: FONT_DISPLAY, fontSize: 17, color: colors.onSurface },
  de: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  sub: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, marginTop: 2 },
}));
