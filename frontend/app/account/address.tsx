import React, { useState } from "react";
import { Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { makeStyles } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useAuth } from "@/src/auth";
import { useMenu } from "@/src/api";
import { Button, Field, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";

/** Add / edit a saved delivery address (modal). `id` param -> edit. */
export default function AddressEditor() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const styles = useStyles();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const toast = useToast();
  const { user, addAddress, updateAddress } = useAuth();
  const { data } = useMenu(0);
  const existing = user?.addresses.find((a) => a.id === id);
  const [f, setF] = useState({ label: existing?.label ?? "", street: existing?.street ?? "", number: existing?.number ?? "", npa: existing?.npa ?? "", city: existing?.city ?? "", instructions: existing?.instructions ?? "" });
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => {
    setF((p) => {
      const next = { ...p, [k]: v };
      if (k === "npa") {
        const z = data?.settings.delivery_zones.find((z) => z.npa === v.trim());
        if (z && !p.city) next.city = z.city;
      }
      return next;
    });
  };

  const submit = async () => {
    if (!f.street.trim() || !f.npa.trim() || !f.city.trim()) {
      toast.show(t("required"), "error");
      return;
    }
    setBusy(true);
    const body = { label: f.label.trim(), street: f.street.trim(), number: f.number.trim(), npa: f.npa.trim(), city: f.city.trim(), instructions: f.instructions.trim() || null };
    try {
      if (existing) await updateAddress(existing.id, body);
      else await addAddress(body);
      toast.show(t("saved"), "success");
      router.back();
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.screen}>
      <ScreenHeader title={existing ? t("editAddress") : t("addAddress")} testID="address-editor-title" />
      <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, gap: 12, paddingBottom: insets.bottom + 120 }} bottomOffset={120}>
        <Field label={t("addressLabel")} value={f.label} onChangeText={set("label")} testID="address-label" />
        <View style={styles.two}>
          <Field label={`${t("street")} *`} value={f.street} onChangeText={set("street")} style={{ flex: 3 }} testID="address-street" />
          <Field label={t("number")} value={f.number} onChangeText={set("number")} style={{ flex: 1 }} testID="address-number" />
        </View>
        <View style={styles.two}>
          <Field label={`${t("npa")} *`} value={f.npa} onChangeText={set("npa")} keyboardType="number-pad" style={{ flex: 1 }} testID="address-npa" />
          <Field label={`${t("city")} *`} value={f.city} onChangeText={set("city")} style={{ flex: 2 }} testID="address-city" />
        </View>
        <Field label={t("deliveryInstructions")} value={f.instructions} onChangeText={set("instructions")} multiline testID="address-instructions" />
        <Text style={styles.hint}>{t("minOrder")}: {data?.settings.delivery_zones.find((z) => z.npa === f.npa.trim())?.minimum_order ?? "–"} CHF</Text>
      </KeyboardAwareScrollView>
      <View style={[styles.cta, { paddingBottom: insets.bottom + 12 }]}>
        <Button title={t("save")} size="lg" icon="check" loading={busy} onPress={submit} testID="address-save" />
      </View>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  two: { flexDirection: "row", gap: 10 },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  cta: { position: "absolute", left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 12, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
}));
