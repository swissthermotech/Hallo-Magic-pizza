import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { shiftsApi, type Shift } from "@/src/api";
import { fmtTime } from "@/src/format";
import { Badge, Button, Field, FONT_DISPLAY, FONT_TEXT, useToast } from "@/src/components/ui";

/** Manager: driver shifts – OUVRIR LE SERVICE (name -> temporary 6-digit PIN), RESET SESSION, FERMER LE SERVICE. */
export function DriverShifts() {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [names, setNames] = useState<Record<string, string>>({});
  const [pins, setPins] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const load = () => shiftsApi.list().then(setShifts).catch((e) => toast.show(e.message, "error"));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (role: string, fn: () => Promise<any>) => {
    setBusy(role);
    try {
      await fn();
      await load();
    } catch (e: any) {
      toast.show(e.message, "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <View style={{ gap: 12 }}>
      <Text style={styles.section}>{t("driverShifts")}</Text>
      {shifts.map((s) => (
        <View key={s.role} style={styles.card} testID={`shift-${s.role}`}>
          <View style={styles.row}>
            <Text style={styles.title}>{s.driver}{s.name ? ` — ${s.name}` : ""}</Text>
            <Badge label={s.name ? (s.connected ? t("connected") : t("shiftOpen")) : t("shiftClosed")} tone={s.name ? (s.connected ? "success" : "warning") : "neutral"} />
          </View>
          {s.name ? (
            <>
              <Text style={styles.hint}>{t("shiftUntil")} {fmtTime(s.expires_at)}</Text>
              {pins[s.role] ? (
                <View style={styles.pinBox} testID={`shift-pin-${s.role}`}>
                  <Text style={styles.pinLabel}>{t("shiftPin")}</Text>
                  <Text style={styles.pin}>{pins[s.role]}</Text>
                  <Text style={styles.hint}>{t("shiftPinHint")}</Text>
                </View>
              ) : null}
              <View style={styles.row}>
                <Button title={t("resetSession")} variant="outline" icon="smartphone" loading={busy === s.role} onPress={() => run(s.role, () => shiftsApi.reset(s.role))} style={{ flex: 1 }} testID={`shift-reset-${s.role}`} />
                <Button title={t("closeShift")} variant="danger" icon="x-circle" loading={busy === s.role} onPress={() => run(s.role, async () => { await shiftsApi.close(s.role); setPins((p) => ({ ...p, [s.role]: "" })); })} style={{ flex: 1 }} testID={`shift-close-${s.role}`} />
              </View>
            </>
          ) : (
            <View style={styles.row}>
              <Field label={t("driverDisplayName")} value={names[s.role] || ""} onChangeText={(v) => setNames((n) => ({ ...n, [s.role]: v }))} style={{ flex: 1 }} autoCapitalize="words" testID={`shift-name-${s.role}`} />
              <Button title={t("openShift")} icon="play" variant="success" loading={busy === s.role} disabled={!(names[s.role] || "").trim()} onPress={() => run(s.role, async () => { const r = await shiftsApi.open(s.role, names[s.role].trim()); setPins((p) => ({ ...p, [s.role]: r.pin || "" })); })} testID={`shift-open-${s.role}`} />
            </View>
          )}
        </View>
      ))}
      <Text style={[styles.hint, { color: colors.muted }]}>{t("shiftHint")}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  section: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10 },
  row: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", gap: 10 },
  title: { fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "800", color: colors.onSurface },
  hint: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  pinBox: { backgroundColor: colors.surfaceInverse, borderRadius: 14, padding: 14, alignItems: "center", gap: 4 },
  pinLabel: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "800", color: colors.onSurfaceInverse, letterSpacing: 1 },
  pin: { fontFamily: FONT_DISPLAY, fontSize: 40, color: colors.onSurfaceInverse, letterSpacing: 6 },
}));
