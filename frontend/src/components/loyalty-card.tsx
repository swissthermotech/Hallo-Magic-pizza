import React from "react";
import { Text, View } from "react-native";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import type { LoyaltySummary } from "@/src/types";
import { FONT_DISPLAY, FONT_TEXT } from "@/src/components/ui";

const fill = (s: string, vars: Record<string, string | number>) => Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), s);

/** Carte Fidélité – 10 stamp positions, progress "n / 10", reward state. Pure display of the server-side summary;
 * used by the customer account (full) and by the Manager customer profile (compact). */
export function LoyaltyCard({ summary, compact = false, testID = "loyalty-card" }: { summary: LoyaltySummary; compact?: boolean; testID?: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const block = summary.block || 10;
  const stamps = Math.max(0, Math.min(block, summary.stamps));
  const left = block - stamps;
  const status = summary.rewards_available > 0
    ? { icon: "gift" as const, tone: "reward" as const, text: fill(t("loyaltyRewardAvailable"), { n: summary.rewards_available }) }
    : summary.rewards_reserved > 0
      ? { icon: "clock" as const, tone: "pending" as const, text: t("loyaltyRewardPending") }
      : left === 1
        ? { icon: "star" as const, tone: "reward" as const, text: t("loyaltyNextOne") }
        : { icon: "target" as const, tone: "neutral" as const, text: fill(t("loyaltyNext"), { n: left }) };

  return (
    <View style={[styles.card, compact && styles.cardCompact]} testID={testID}>
      <View style={styles.head}>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>{t("loyaltyTitle")}</Text>
          <Text style={styles.subtitle}>{t("loyaltySubtitle")}</Text>
        </View>
        <Text style={styles.progress} testID={`${testID}-progress`}>{stamps} / {block}</Text>
      </View>
      <View style={styles.grid} accessibilityLabel={`${t("loyaltyProgress")} ${stamps}/${block}`}>
        {Array.from({ length: block }).map((_, i) => {
          const filled = i < stamps;
          const isReward = i === block - 1;
          return (
            <View key={i} style={[styles.stamp, filled && styles.stampFilled, isReward && !filled && styles.stampReward]} testID={`${testID}-stamp-${i + 1}`}>
              {isReward ? (
                <Text style={[styles.rewardText, filled && styles.rewardTextFilled]}>-50%</Text>
              ) : (
                <Feather name={filled ? "check" : "circle"} size={filled ? 16 : 8} color={filled ? colors.onSurfaceInverse : colors.borderStrong} />
              )}
            </View>
          );
        })}
      </View>
      <View style={[styles.status, status.tone === "reward" && styles.statusReward, status.tone === "pending" && styles.statusPending]} testID={`${testID}-status`}>
        <Feather name={status.icon} size={16} color={status.tone === "reward" ? colors.brandPrimary : colors.onSurfaceSecondary} />
        <Text style={[styles.statusText, status.tone === "reward" && styles.statusTextReward]}>{status.text}</Text>
      </View>
      {!compact ? <Text style={styles.rule}>{t("loyaltyRule")}</Text> : null}
      <Text style={styles.hint}>
        {t("loyaltyStampsFinal")}
        {summary.lifetime_pizzas > 0 ? ` ${fill(t("loyaltyLifetime"), { n: summary.lifetime_pizzas, r: summary.rewards_used })}` : ""}
      </Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 12 },
  cardCompact: { padding: 14, gap: 10 },
  head: { flexDirection: "row", alignItems: "center", gap: 12 },
  title: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  subtitle: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.brandPrimary, marginTop: 2 },
  progress: { fontFamily: FONT_DISPLAY, fontSize: 24, color: colors.onSurface },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  stamp: { width: 44, height: 44, borderRadius: 22, borderWidth: 1.5, borderColor: colors.borderStrong, borderStyle: "dashed", alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
  stampFilled: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary, borderStyle: "solid" },
  stampReward: { borderColor: colors.brandPrimary, backgroundColor: colors.brandSoft },
  rewardText: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "900", color: colors.brandPrimary },
  rewardTextFilled: { color: colors.onSurfaceInverse },
  status: { flexDirection: "row", alignItems: "center", gap: 8, padding: 10, borderRadius: 12, backgroundColor: colors.surfaceTertiary },
  statusReward: { backgroundColor: colors.brandSoft },
  statusPending: { backgroundColor: colors.surfaceTertiary },
  statusText: { flex: 1, fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "700", color: colors.onSurfaceSecondary, lineHeight: 19 },
  statusTextReward: { color: colors.brandPrimary },
  rule: { fontFamily: FONT_TEXT, fontSize: 13, lineHeight: 19, color: colors.onSurfaceSecondary },
  hint: { fontFamily: FONT_TEXT, fontSize: 12, lineHeight: 17, color: colors.muted },
}));
