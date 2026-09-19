import React from "react";
import { Pressable, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { makeStyles } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { FONT_TEXT } from "@/src/components/ui";

/** Public footer: legal links (texts managed in Administration) + copyright. No staff/test links on the customer site. */
export function LegalFooter({ name }: { name?: string }) {
  const styles = useStyles();
  const router = useRouter();
  const { t } = useI18n();
  return (
    <View style={styles.footer} testID="legal-footer">
      <View style={styles.legalRow} testID="legal-links">
        {(["privacy", "terms", "imprint"] as const).map((k) => (
          <Pressable key={k} testID={`legal-link-${k}`} onPress={() => router.push({ pathname: "/legal/[kind]", params: { kind: k } })} style={styles.legalLink}>
            <Text style={styles.legalText}>{t(k === "privacy" ? "legalPrivacy" : k === "terms" ? "legalTerms" : "legalImprint")}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.copy}>© {new Date().getFullYear()} {name || "Hallo Magic Pizza"}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  footer: { alignItems: "center", paddingTop: 24, paddingBottom: 8, gap: 4 },
  legalRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 6 },
  legalLink: { paddingVertical: 10, paddingHorizontal: 10, minHeight: 44, justifyContent: "center" },
  legalText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.onSurfaceSecondary, textDecorationLine: "underline" },
  copy: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, textAlign: "center" },
}));
