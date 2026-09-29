import React, { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { staffCredentials } from "@/src/api";
import { useStaff } from "@/src/staff-auth";
import { DriverShifts } from "@/src/components/driver-shifts";
import { Badge, Button, Field, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";

type RoleRow = { role: string; label: string; active: boolean; credential: "password" | "pin" | "none" };

/** Client-side mirror of the server rules (the server is authoritative). Each rule is shown live under the fields so the
 * user always sees WHY a password is not accepted; the Save button is only disabled while a field is still empty. */
const RULES: { key: "ruleLength" | "ruleLetter" | "ruleDigit" | "ruleSpecial" | "ruleNoSpaces"; test: (p: string) => boolean }[] = [
  { key: "ruleLength", test: (p) => p.length >= 10 && p.length <= 128 },
  { key: "ruleLetter", test: (p) => /[A-Za-z]/.test(p) },
  { key: "ruleDigit", test: (p) => /[0-9]/.test(p) },
  { key: "ruleSpecial", test: (p) => /[^A-Za-z0-9\s]/.test(p) },
  { key: "ruleNoSpaces", test: (p) => p === p.trim() },
];
const failingRule = (p: string) => RULES.find((r) => !r.test(p))?.key ?? null;

/** Manager only: set the password of each staff role (verified & stored hashed on the server; legacy PINs are replaced). */
export default function SecurityScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const toast = useToast();
  const { adoptToken } = useStaff();
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [pw, setPw] = useState<Record<string, string>>({});
  const [confirm, setConfirm] = useState<Record<string, string>>({});
  const [show, setShow] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    staffCredentials.roles().then(setRoles).catch((e) => toast.show(e.message, "error"));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (role: string) => {
    const password = pw[role] || "";
    const failing = failingRule(password);
    if (failing) {
      toast.show(`${t(failing)} – ${t("passwordRules")}`, "error");
      return;
    }
    if (password !== (confirm[role] || "")) {
      toast.show(t("passwordMismatch"), "error");
      return;
    }
    setBusy(role);
    try {
      const r = await staffCredentials.setPassword(role, password);
      if (r.access_token) await adoptToken(r.access_token); // own password changed -> keep this device logged in
      setPw((p) => ({ ...p, [role]: "" }));
      setConfirm((p) => ({ ...p, [role]: "" }));
      setRoles((rs) => rs.map((x) => (x.role === role ? { ...x, credential: "password" } : x)));
      toast.show(t("passwordSaved"), "success");
    } catch (e: any) {
      toast.show(e.message, "error");
    } finally {
      setBusy(null);
    }
  };

  const legacy = roles.filter((r) => !r.role.startsWith("driver") && r.credential !== "password");

  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("security")} subtitle={t("securityHint")} testID="security-title" />
      <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, gap: 12, paddingBottom: insets.bottom + 40 }} bottomOffset={40}>
        <DriverShifts />
        <Text style={styles.label}>{t("staffPasswords")}</Text>
        {legacy.length ? (
          <View style={styles.warn} testID="security-legacy-warning">
            <Feather name="alert-triangle" size={18} color={colors.error} />
            <Text style={styles.warnText}>{t("legacyPinWarning")}: {legacy.map((r) => r.label).join(", ")}</Text>
          </View>
        ) : null}
        <Text style={styles.hint}>{t("passwordRules")}</Text>
        {roles.filter((r) => !r.role.startsWith("driver")).map((r) => (
          <View key={r.role} style={styles.card} testID={`security-role-${r.role}`}>
            <View style={styles.row}>
              <Text style={styles.label}>{r.label}</Text>
              <Badge label={r.credential === "password" ? t("passwordSet") : t("legacyPin")} tone={r.credential === "password" ? "success" : "warning"} testID={`security-credential-${r.role}`} />
            </View>
            <View style={{ flexDirection: "row", gap: 10, alignItems: "flex-end" }}>
              <Field label={t("newPassword")} value={pw[r.role] || ""} onChangeText={(v) => setPw((p) => ({ ...p, [r.role]: v }))} secureTextEntry={!show[r.role]} autoCapitalize="none" autoCorrect={false} spellCheck={false} autoComplete="off" importantForAutofill="no" maxLength={128} style={{ flex: 1 }} testID={`security-password-${r.role}`} />
              <Pressable testID={`security-show-${r.role}`} onPress={() => setShow((s) => ({ ...s, [r.role]: !s[r.role] }))} accessibilityRole="button" accessibilityLabel={show[r.role] ? t("hidePassword") : t("showPassword")} style={styles.eye}>
                <Feather name={show[r.role] ? "eye-off" : "eye"} size={20} color={colors.muted} />
              </Pressable>
            </View>
            <View style={{ flexDirection: "row", gap: 10, alignItems: "flex-end" }}>
              <Field label={t("confirmPassword")} value={confirm[r.role] || ""} onChangeText={(v) => setConfirm((p) => ({ ...p, [r.role]: v }))} secureTextEntry={!show[r.role]} autoCapitalize="none" autoCorrect={false} spellCheck={false} autoComplete="off" importantForAutofill="no" maxLength={128} style={{ flex: 1 }} testID={`security-confirm-${r.role}`} />
              <Button title={t("save")} icon="key" loading={busy === r.role} disabled={!(pw[r.role] || "").length || !(confirm[r.role] || "").length} onPress={() => save(r.role)} testID={`security-save-${r.role}`} />
            </View>
            {(pw[r.role] || "").length ? (
              <View style={styles.checks} testID={`security-checks-${r.role}`}>
                {RULES.map((rule) => {
                  const ok = rule.test(pw[r.role] || "");
                  return (
                    <View key={rule.key} style={styles.check}>
                      <Feather name={ok ? "check-circle" : "x-circle"} size={14} color={ok ? colors.success : colors.error} />
                      <Text style={[styles.checkText, !ok && { color: colors.error }]}>{t(rule.key)}</Text>
                    </View>
                  );
                })}
                <View style={styles.check}>
                  <Feather name={(pw[r.role] || "") === (confirm[r.role] || "") ? "check-circle" : "x-circle"} size={14} color={(pw[r.role] || "") === (confirm[r.role] || "") ? colors.success : colors.error} />
                  <Text style={[styles.checkText, (pw[r.role] || "") !== (confirm[r.role] || "") && { color: colors.error }]}>{t("ruleMatch")}</Text>
                </View>
              </View>
            ) : null}
          </View>
        ))}
        <Text style={styles.hint}>{t("passwordChangeHint")}</Text>
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
  warn: { flexDirection: "row", gap: 10, alignItems: "center", backgroundColor: colors.warningSoft, borderRadius: 14, padding: 12 },
  warnText: { flex: 1, fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.onSurface },
  eye: { width: 48, height: 48, alignItems: "center", justifyContent: "center", borderRadius: 24, backgroundColor: colors.surfaceTertiary },
  checks: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 2 },
  check: { flexDirection: "row", alignItems: "center", gap: 4 },
  checkText: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
}));
