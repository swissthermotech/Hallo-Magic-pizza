import React, { useState } from "react";
import { Modal, Pressable, Text, View } from "react-native";
import { makeStyles } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useAdjustCustomerLoyalty } from "@/src/api";
import { fmtDate, fmtTime } from "@/src/format";
import { Button, FONT_DISPLAY, FONT_TEXT, useToast } from "@/src/components/ui";
import type { LoyaltyAuditEntry } from "@/src/types";

const fill = (s: string, vars: Record<string, string | number>) => Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), s);

/** Manager-only: set a customer account's current-cycle stamps (0..9) with an explicit confirmation.
 * Rewards / statistics are not editable; the server journals every change (shown below the control). */
export function LoyaltyAdjust({ customerKey, customerName, stamps, audit }: { customerKey: string; customerName: string; stamps: number; audit: LoyaltyAuditEntry[] }) {
  const styles = useStyles();
  const { t } = useI18n();
  const toast = useToast();
  const adjust = useAdjustCustomerLoyalty();
  const [value, setValue] = useState<number | null>(null);
  const [confirm, setConfirm] = useState(false);
  const target = value ?? stamps;
  const changed = target !== stamps;

  const save = () => {
    setConfirm(false);
    adjust.mutateAsync({ key: customerKey, stamps: target })
      .then(() => { setValue(null); toast.show(t("loyaltyAdjustDone"), "success"); })
      .catch((e) => toast.show(e.message, "error"));
  };

  return (
    <View style={styles.card} testID="loyalty-adjust">
      <Text style={styles.title}>{t("loyaltyAdjustTitle")}</Text>
      <Text style={styles.hint}>{t("loyaltyAdjustHint")}</Text>
      <View style={styles.row}>
        {Array.from({ length: 10 }).map((_, n) => {
          const selected = n === target;
          return (
            <Pressable key={n} onPress={() => setValue(n)} style={[styles.chip, selected && styles.chipSelected, n === stamps && !selected && styles.chipCurrent]} testID={`loyalty-adjust-${n}`}
              accessibilityRole="button" accessibilityState={{ selected }}>
              <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{n}</Text>
            </Pressable>
          );
        })}
      </View>
      <Button title={`${t("save")} · ${target} / 10`} onPress={() => setConfirm(true)} disabled={!changed || adjust.isPending} loading={adjust.isPending} testID="loyalty-adjust-save" />
      {audit.length > 0 ? (
        <View style={{ gap: 4 }} testID="loyalty-audit">
          <Text style={styles.auditTitle}>{t("loyaltyAuditTitle")}</Text>
          {audit.map((a) => (
            <Text key={a.id} style={styles.auditLine} testID={`loyalty-audit-${a.id}`}>
              {a.at ? `${fmtDate(a.at)} ${fmtTime(a.at)}` : "–"} · {a.previous} → {a.new} · {a.manager || "manager"}
            </Text>
          ))}
        </View>
      ) : null}

      <Modal visible={confirm} transparent animationType="fade" onRequestClose={() => setConfirm(false)}>
        <View style={styles.backdrop}>
          <View style={styles.modal} testID="loyalty-adjust-confirm">
            <Text style={styles.modalTitle}>{t("loyaltyAdjustTitle")}</Text>
            <Text style={styles.modalText}>{fill(t("loyaltyAdjustConfirm"), { a: stamps, b: target, name: customerName })}</Text>
            <View style={{ flexDirection: "row", gap: 10 }}>
              <Button title={t("close")} variant="secondary" onPress={() => setConfirm(false)} style={{ flex: 1 }} testID="loyalty-adjust-cancel" />
              <Button title={t("save")} onPress={save} style={{ flex: 1 }} testID="loyalty-adjust-ok" />
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10, marginTop: 10 },
  title: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.onSurface },
  hint: { fontFamily: FONT_TEXT, fontSize: 12, lineHeight: 17, color: colors.muted },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  chipCurrent: { borderColor: colors.brandPrimary, borderStyle: "dashed" },
  chipSelected: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  chipText: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.onSurface },
  chipTextSelected: { color: colors.onSurfaceInverse },
  auditTitle: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8, marginTop: 4 },
  auditLine: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.onSurfaceSecondary },
  backdrop: { flex: 1, backgroundColor: colors.scrim, alignItems: "center", justifyContent: "center", padding: 24 },
  modal: { width: "100%", maxWidth: 420, backgroundColor: colors.surface, borderRadius: 20, padding: 20, gap: 14 },
  modalTitle: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
  modalText: { fontFamily: FONT_TEXT, fontSize: 14, lineHeight: 20, color: colors.onSurfaceSecondary },
}));
