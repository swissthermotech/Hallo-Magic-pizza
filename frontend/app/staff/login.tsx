import React, { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAvoidingView } from "react-native-keyboard-controller";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { homeFor, useStaff } from "@/src/staff-auth";
import { BACKEND_HOST, PRODUCTION_BACKEND_URL } from "@/src/api";
import { Button, FONT_DISPLAY, FONT_TEXT, ScreenHeader } from "@/src/components/ui";

/** Staff login: real password (manager / kitchen / phone) or the driver's temporary 6-digit shift code.
 * Verified server-side (Argon2), 5 failures => 15-minute lockout enforced by the backend. Characters are always hidden by default. */
export default function StaffLogin() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const { unlock, lastError, unlocked, label } = useStaff();
  const { switch: switching } = useLocalSearchParams<{ switch?: string }>();
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  const submit = async () => {
    if (!password.trim() || busy) return;
    setBusy(true);
    const role = await unlock(password);
    setBusy(false);
    if (role) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      setPassword("");
      router.replace(homeFor(role));
    } else {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
      setError(true);
      setPassword("");
    }
  };

  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("staffAccess")} subtitle={switching && unlocked ? `${t("sessionActive")}: ${label} – ${t("switchAccountHint")}` : undefined} testID="staff-login-title" />
      <KeyboardAvoidingView behavior="padding" style={{ flex: 1 }} keyboardVerticalOffset={16}>
        <View style={[styles.body, { paddingBottom: insets.bottom + 24 }]}>
          <View style={styles.lockIcon}><Feather name="lock" size={30} color={colors.onSurfaceInverse} /></View>
          <Text style={styles.title}>Hallo Magic Pizza</Text>
          <Text style={styles.hint}>{t("staffPinHint")}</Text>
          <View style={[styles.inputRow, error && { borderColor: colors.error }]}>
            <TextInput
              testID="staff-password-input"
              value={password}
              onChangeText={(v) => { setPassword(v); setError(false); }}
              placeholder={t("staffPin")}
              placeholderTextColor={colors.muted}
              secureTextEntry={!show}
              autoCapitalize="none"
              autoCorrect={false}
              spellCheck={false}
              textContentType="password"
              autoComplete="off"
              importantForAutofill="no"
              maxLength={128}
              returnKeyType="go"
              onSubmitEditing={submit}
              style={styles.input}
            />
            <Pressable testID="staff-password-toggle" onPress={() => setShow((s) => !s)} hitSlop={8} accessibilityRole="button" accessibilityLabel={show ? t("hidePassword") : t("showPassword")} style={styles.eye}>
              <Feather name={show ? "eye-off" : "eye"} size={20} color={colors.muted} />
            </Pressable>
          </View>
          {error || lastError ? <Text style={styles.error} testID="staff-pin-error">{lastError || t("wrongPin")}</Text> : null}
          <Button title={t("unlock")} size="lg" icon="unlock" onPress={submit} loading={busy} disabled={password.trim().length === 0} testID="staff-pin-submit" />
          {/* Which backend this device talks to – staff can see at a glance that they are on PRODUCTION */}
          <Text style={styles.server} testID="staff-backend-host">
            {t("server")}: {BACKEND_HOST}{`https://${BACKEND_HOST}` === PRODUCTION_BACKEND_URL ? ` · ${t("production")}` : ` · ${t("testEnvironment")}`}
          </Text>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  body: { flex: 1, justifyContent: "center", padding: 24, gap: 14 },
  lockIcon: { width: 72, height: 72, borderRadius: 36, backgroundColor: colors.surfaceInverse, alignItems: "center", justifyContent: "center", alignSelf: "center", marginBottom: 6 },
  title: { fontFamily: FONT_DISPLAY, fontSize: 28, color: colors.onSurface, textAlign: "center" },
  hint: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.muted, textAlign: "center", marginBottom: 10 },
  inputRow: { height: 60, borderRadius: 16, backgroundColor: colors.surfaceSecondary, borderWidth: 1.5, borderColor: colors.border, flexDirection: "row", alignItems: "center", paddingLeft: 18, paddingRight: 6 },
  input: { flex: 1, height: "100%", fontFamily: FONT_TEXT, fontSize: 18, color: colors.onSurface },
  eye: { width: 48, height: 48, alignItems: "center", justifyContent: "center", borderRadius: 24 },
  error: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.error, textAlign: "center", fontWeight: "700" },
  server: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, textAlign: "center", marginTop: 8 },
}));
