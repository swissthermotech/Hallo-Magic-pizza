import React from "react";
import { Pressable, Text, View } from "react-native";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { FONT_TEXT } from "@/src/components/ui";
import type { Lang, OrderType } from "@/src/types";

export const WEEKDAYS: Record<Lang, string[]> = {
  fr: ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"],
  de: ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"],
};

/** "2026-10-23" -> "jeudi 23.10.2026" (customer language). */
export function fmtRequestedDate(iso: string, lang: Lang): string {
  const day = new Date(`${iso}T12:00:00`).getDay();
  return `${WEEKDAYS[lang][day]} ${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}`;
}

/**
 * LIVRAISON / RETRAIT SUR PLACE banner – two clearly different colours (tomato = delivery, olive = pickup) so the
 * customer cannot mistake one for the other. Used right above the final "Confirmer la commande" button and again on
 * the order status page. `compact` = one line (keyboard open on the checkout).
 */
export function OrderTypeBanner({ type, compact, detail, testID, children }: { type: OrderType; compact?: boolean; detail?: string; testID: string; children?: React.ReactNode }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const delivery = type === "delivery";
  const fg = delivery ? colors.onBrandPrimary : colors.onBrandSecondary;
  return (
    <View style={[styles.card, delivery ? styles.cardDelivery : styles.cardPickup, compact && styles.cardCompact]} testID={testID}>
      <View style={styles.head}>
        <View style={[styles.pill, { backgroundColor: delivery ? colors.brandPrimary : colors.brandSecondary }]} testID={`${testID}-type`}>
          <Feather name={delivery ? "truck" : "shopping-bag"} size={16} color={fg} />
          <Text style={[styles.pillText, { color: fg }]}>{delivery ? t("delivery").toUpperCase() : t("pickupOnSite")}</Text>
        </View>
        {compact && detail ? <Text style={styles.compactDetail} numberOfLines={1} testID={`${testID}-detail`}>{detail}</Text> : null}
      </View>
      {!compact && children ? <View style={styles.rows}>{children}</View> : null}
    </View>
  );
}

/** One line of the banner: icon + text (+ optional small "Modifier" link or a right element). */
export function SummaryRow({ icon, text, missing, onEdit, right, testID }: { icon: React.ComponentProps<typeof Feather>["name"]; text: string; missing?: boolean; onEdit?: () => void; right?: React.ReactNode; testID: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  return (
    <View style={styles.row} testID={testID}>
      <Feather name={icon} size={15} color={missing ? colors.error : colors.onSurfaceSecondary} style={{ marginTop: 2 }} />
      <Text style={[styles.rowText, missing && styles.rowTextMissing]} numberOfLines={2} testID={`${testID}-text`}>{text}</Text>
      {right}
      {onEdit ? (
        <Pressable onPress={onEdit} hitSlop={10} style={styles.edit} testID={`${testID}-edit`} accessibilityRole="button" accessibilityLabel={t("edit")}>
          <Feather name="edit-2" size={12} color={colors.brandSecondary} />
          <Text style={styles.editText}>{t("edit")}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  card: { borderRadius: 14, borderWidth: 1.5, padding: 10, gap: 8 },
  cardDelivery: { backgroundColor: colors.brandSoft, borderColor: colors.brandPrimary },
  cardPickup: { backgroundColor: colors.successSoft, borderColor: colors.brandSecondary },
  cardCompact: { paddingVertical: 6 },
  head: { flexDirection: "row", alignItems: "center", gap: 10 },
  pill: { flexDirection: "row", alignItems: "center", gap: 6, borderRadius: 999, paddingHorizontal: 12, height: 30 },
  pillText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "900", letterSpacing: 1 },
  compactDetail: { flex: 1, fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.onSurface },
  rows: { gap: 6 },
  row: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  rowText: { flex: 1, fontFamily: FONT_TEXT, fontSize: 14, lineHeight: 19, fontWeight: "600", color: colors.onSurface },
  rowTextMissing: { color: colors.error },
  edit: { flexDirection: "row", alignItems: "center", gap: 4, minHeight: 24, paddingHorizontal: 4 },
  editText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.brandSecondary, textDecorationLine: "underline" },
}));
