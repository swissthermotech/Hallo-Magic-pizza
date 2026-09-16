import React, { useState } from "react";
import { Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAvoidingView } from "react-native-keyboard-controller";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { homeFor, useStaff } from "@/src/staff-auth";
import { Button, FONT_DISPLAY, FONT_TEXT, ScreenHeader } from "@/src/components/ui";

export default function StaffLogin() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const { unlock, lastError } = useStaff();
  const [pin, setPin] = useState("");
  const [error, setError] = useState(false);

  const submit = async () => {
    const role = await unlock(pin);
    if (role) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      router.replace(homeFor(role));
    } else {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
      setError(true);
      setPin("");
    }
  };

  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("staffAccess")} testID="staff-login-title" />
      <KeyboardAvoidingView behavior="padding" style={{ flex: 1 }} keyboardVerticalOffset={16}>
        <View style={[styles.body, { paddingBottom: insets.bottom + 24 }]}>
          <View style={styles.lockIcon}><Feather name="lock" size={30} color={colors.onSurfaceInverse} /></View>
          <Text style={styles.title}>Hallo Magic Pizza</Text>
          <Text style={styles.hint}>{t("staffPinHint")}</Text>
          <TextInput
            testID="staff-pin-input"
            value={pin}
            onChangeText={(v) => { setPin(v); setError(false); }}
            placeholder={t("staffPin")}
            placeholderTextColor={colors.muted}
            keyboardType="number-pad"
            secureTextEntry
            maxLength={8}
            onSubmitEditing={submit}
            style={[styles.input, error && { borderColor: colors.error }]}
          />
          {error ? <Text style={styles.error} testID="staff-pin-error">{lastError || t("wrongPin")}</Text> : null}
          <Button title={t("unlock")} size="lg" icon="unlock" onPress={submit} disabled={pin.length < 4} testID="staff-pin-submit" />
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
  input: { height: 60, borderRadius: 16, backgroundColor: colors.surfaceSecondary, borderWidth: 1.5, borderColor: colors.border, textAlign: "center", fontFamily: FONT_TEXT, fontSize: 26, letterSpacing: 8, color: colors.onSurface },
  error: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.error, textAlign: "center", fontWeight: "700" },
}));
