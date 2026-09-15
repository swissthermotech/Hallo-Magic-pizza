import React, { useEffect, useState } from "react";
import { ActivityIndicator, Switch, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu, useSaveSettings } from "@/src/api";
import { Button, Field, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast, VatPicker } from "@/src/components/ui";
import type { Settings } from "@/src/types";

const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export default function SettingsScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const toast = useToast();
  const { data } = useMenu(0);
  const save = useSaveSettings();
  const [s, setS] = useState<Settings | null>(null);
  const [zonesText, setZonesText] = useState("");

  useEffect(() => {
    if (data && !s) {
      setS(data.settings);
      setZonesText(data.settings.delivery_zones.map((z) => `${z.npa} | ${z.city} | ${z.minimum_order}`).join("\n"));
    }
  }, [data, s]);

  if (!s) return <View style={[styles.screen, styles.center]}><ActivityIndicator color={colors.brandPrimary} /></View>;

  const num = (v: string) => parseFloat(v.replace(",", ".")) || 0;
  const submit = async () => {
    const zones = zonesText.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
      const [npa, city, min] = l.split("|").map((x) => x.trim());
      return { npa, city: city || "", minimum_order: num(min || "0") };
    });
    try {
      await save.mutateAsync({ ...s, delivery_zones: zones });
      toast.show(t("saved"), "success");
      router.back();
    } catch (e: any) {
      toast.show(e.message, "error");
    }
  };

  const Row = ({ label, k, testID }: { label: string; k: "temporarily_closed" | "delivery_enabled" | "pickup_enabled"; testID: string }) => (
    <View style={styles.switchRow}>
      <Text style={styles.switchLabel}>{label}</Text>
      <Switch testID={testID} value={s[k]} onValueChange={(v) => setS({ ...s, [k]: v })} trackColor={{ true: k === "temporarily_closed" ? colors.error : colors.success, false: colors.borderStrong }} thumbColor={colors.surfaceSecondary} />
    </View>
  );

  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("settings")} testID="settings-title" />
      <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, gap: 14, paddingBottom: insets.bottom + 120 }} bottomOffset={140}>
        <Field label="Restaurant" value={s.restaurant_name} onChangeText={(v) => setS({ ...s, restaurant_name: v })} testID="settings-name" />

        <Text style={styles.section}>{t("fiscal")}</Text>
        <Field label={t("businessName")} value={s.business_name} onChangeText={(v) => setS({ ...s, business_name: v })} testID="settings-business-name" />
        <Field label={t("street")} value={s.street} onChangeText={(v) => setS({ ...s, street: v, address: `${v}, ${s.postal_code} ${s.city}` })} testID="settings-street" />
        <View style={{ flexDirection: "row", gap: 10 }}>
          <Field label={t("postalCode")} value={s.postal_code} onChangeText={(v) => setS({ ...s, postal_code: v, address: `${s.street}, ${v} ${s.city}` })} style={{ flex: 1 }} testID="settings-postal-code" />
          <Field label={t("city")} value={s.city} onChangeText={(v) => setS({ ...s, city: v, address: `${s.street}, ${s.postal_code} ${v}` })} style={{ flex: 2 }} testID="settings-city" />
        </View>
        <Field label={t("phone")} value={s.phone} onChangeText={(v) => setS({ ...s, phone: v })} testID="settings-phone" />
        <Field label={t("vatNumber")} value={s.vat_number} onChangeText={(v) => setS({ ...s, vat_number: v })} testID="settings-vat-number" />
        <VatPicker label={t("vatStandard")} value={s.vat_rate_standard} onChange={(v) => setS({ ...s, vat_rate_standard: v })} testID="settings-vat-standard" />
        <VatPicker label={t("vatAlcohol")} value={s.vat_rate_alcohol} onChange={(v) => setS({ ...s, vat_rate_alcohol: v })} testID="settings-vat-alcohol" />
        <VatPicker label={t("vatDelivery")} value={s.delivery_fee_vat_rate} onChange={(v) => setS({ ...s, delivery_fee_vat_rate: v })} testID="settings-vat-delivery" />

        <Text style={styles.section}>{t("settings")}</Text>
        <Row label={t("tempClosed")} k="temporarily_closed" testID="settings-closed" />
        <Row label={t("pickupOnOff")} k="pickup_enabled" testID="settings-pickup" />
        <Row label={t("deliveryOnOff")} k="delivery_enabled" testID="settings-delivery" />

        <Text style={styles.section}>{t("delivery")}</Text>
        <View style={{ flexDirection: "row", gap: 10 }}>
          <Field label={t("minimumOrder")} value={String(s.minimum_order)} onChangeText={(v) => setS({ ...s, minimum_order: num(v) })} keyboardType="decimal-pad" style={{ flex: 1 }} testID="settings-minimum" />
          <Field label={t("deliveryFeeLabel")} value={String(s.delivery_fee)} onChangeText={(v) => setS({ ...s, delivery_fee: num(v) })} keyboardType="decimal-pad" style={{ flex: 1 }} testID="settings-fee" />
        </View>
        <Field label={t("zones")} value={zonesText} onChangeText={setZonesText} multiline style={{ minHeight: 200 }} testID="settings-zones" />

        <Text style={styles.section}>{t("hours")}</Text>
        {DAY_KEYS.map((d) => (
          <Field key={d} label={d.toUpperCase()} value={s.opening_hours[d] ?? ""} onChangeText={(v) => setS({ ...s, opening_hours: { ...s.opening_hours, [d]: v } })} testID={`settings-hours-${d}`} />
        ))}
      </KeyboardAwareScrollView>
      <View style={[styles.cta, { paddingBottom: insets.bottom + 12 }]}>
        <Button title={t("save")} size="lg" icon="check" loading={save.isPending} onPress={submit} testID="settings-save" />
      </View>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  center: { alignItems: "center", justifyContent: "center" },
  section: { fontFamily: FONT_DISPLAY, fontSize: 19, color: colors.onSurface, marginTop: 6 },
  switchRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", backgroundColor: colors.surfaceSecondary, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14, height: 52 },
  switchLabel: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "600", color: colors.onSurface },
  cta: { position: "absolute", left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 12, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
}));
