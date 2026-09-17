import React, { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { makeStyles } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { staffPins } from "@/src/api";
import { DriverShifts } from "@/src/components/driver-shifts";
import { Button, Field, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";

/** Manager only: change the access code of each role (verified & stored hashed on the server). */
export default function SecurityScreen() {
  const styles = useStyles();
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const toast = useToast();
  const [roles, setRoles] = useState<{ role: string; label: string; active: boolean }[]>([]);
  const [pins, setPins] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    staffPins.roles().then(setRoles).catch((e) => toast.show(e.message, "error"));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleActive = async (role: string, active: boolean) => {
    try {
      await staffPins.setActive(role, active);
      setRoles((rs) => rs.map((r) => (r.role === role ? { ...r, active } : r)));
      toast.show(t("saved"), "success");
    } catch (e: any) {
      toast.show(e.message, "error");
    }
  };

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
        <DriverShifts />
        <Text style={styles.label}>{t("security")}</Text>
        {roles.filter((r) => !r.role.startsWith("driver")).map((r) => (
          <View key={r.role} style={styles.card} testID={`security-role-${r.role}`}>
            <View style={styles.row}>
              <Text style={styles.label}>{r.label}</Text>
              {r.role.startsWith("driver") ? (
                <View style={styles.segment}>
                  <Pressable testID={`driver-active-on-${r.role}`} onPress={() => toggleActive(r.role, true)} style={[styles.seg, r.active && styles.segOn]}><Text style={[styles.segText, r.active && styles.segTextOn]}>{t("activePos")}</Text></Pressable>
                  <Pressable testID={`driver-active-off-${r.role}`} onPress={() => toggleActive(r.role, false)} style={[styles.seg, !r.active && styles.segOff]}><Text style={[styles.segText, !r.active && styles.segTextOn]}>{t("inactivePos")}</Text></Pressable>
                </View>
              ) : null}
            </View>
            {r.role.startsWith("driver") ? <Text style={styles.hint}>{t("shiftHint")}</Text> : null}
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
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 10 },
  hint: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  segment: { flexDirection: "row", backgroundColor: colors.surfaceTertiary, borderRadius: 999, padding: 3 },
  seg: { height: 36, paddingHorizontal: 14, borderRadius: 999, justifyContent: "center" },
  segOn: { backgroundColor: colors.success },
  segOff: { backgroundColor: colors.error },
  segText: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "900", color: colors.onSurfaceSecondary },
  segTextOn: { color: colors.onSuccess },
}));
