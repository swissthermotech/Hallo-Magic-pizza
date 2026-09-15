import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { makeStyles } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { staffPins } from "@/src/api";
import { Button, Field, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";

/** Manager only: change the access code of each role (verified & stored hashed on the server). */
export default function SecurityScreen() {
  const styles = useStyles();
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const toast = useToast();
  const [roles, setRoles] = useState<{ role: string; label: string }[]>([]);
  const [pins, setPins] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    staffPins.roles().then(setRoles).catch((e) => toast.show(e.message, "error"));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (role: string) => {
    const pin = (pins[role] || "").trim();
    if (!/^\d{4,8}$/.test(pin)) {
      toast.show(t("securityHint"), "error");
      return;
    }
    setBusy(role);
    try {
      await staffPins.change(role, pin);
      setPins((p) => ({ ...p, [role]: "" }));
      toast.show(t("saved"), "success");
    } catch (e: any) {
      toast.show(e.message, "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("security")} subtitle={t("securityHint")} testID="security-title" />
      <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, gap: 12, paddingBottom: insets.bottom + 40 }} bottomOffset={40}>
        {roles.map((r) => (
          <View key={r.role} style={styles.card} testID={`security-role-${r.role}`}>
            <Text style={styles.label}>{r.label}</Text>
            <View style={{ flexDirection: "row", gap: 10, alignItems: "flex-end" }}>
              <Field label={t("newPin")} value={pins[r.role] || ""} onChangeText={(v) => setPins((p) => ({ ...p, [r.role]: v }))} keyboardType="number-pad" secureTextEntry maxLength={8} style={{ flex: 1 }} testID={`security-pin-${r.role}`} />
              <Button title={t("save")} icon="key" loading={busy === r.role} onPress={() => save(r.role)} testID={`security-save-${r.role}`} />
            </View>
          </View>
        ))}
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 8 },
  label: { fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "800", color: colors.onSurface },
}));
