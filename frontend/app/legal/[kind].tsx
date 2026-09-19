import React from "react";
import { ScrollView, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { makeStyles } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu } from "@/src/api";
import { FONT_TEXT, ScreenHeader } from "@/src/components/ui";

type Kind = "privacy" | "terms" | "imprint";
const FIELD = { privacy: "legal_privacy", terms: "legal_terms", imprint: "legal_imprint" } as const;
const LABEL = { privacy: "legalPrivacy", terms: "legalTerms", imprint: "legalImprint" } as const;

/** Public legal page (Confidentialité / CGV / Mentions légales). The text is entered by the restaurant in
 *  Administration → Réglages → Textes légaux; until then a neutral placeholder is shown (no invented legal content). */
export default function LegalPage() {
  const styles = useStyles();
  const insets = useSafeAreaInsets();
  const { t, tx } = useI18n();
  const { kind } = useLocalSearchParams<{ kind: string }>();
  const k: Kind = kind === "terms" || kind === "imprint" ? kind : "privacy";
  const { data } = useMenu();
  const text = tx(data?.settings?.[FIELD[k]] ?? { fr: "", de: "" }).trim();
  return (
    <View style={styles.screen}>
      <ScreenHeader title={t(LABEL[k])} testID={`legal-title-${k}`} />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + 24 }]}>
        <Text style={[styles.body, !text && styles.placeholder]} testID={`legal-body-${k}`}>{text || t("legalPlaceholder")}</Text>
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  content: { padding: 20, width: "100%", maxWidth: 760, alignSelf: "center" },
  body: { fontFamily: FONT_TEXT, fontSize: 15, lineHeight: 24, color: colors.onSurface },
  placeholder: { color: colors.muted, fontStyle: "italic" },
}));
