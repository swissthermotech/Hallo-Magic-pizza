import React, { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu, useSetFirstDelivery } from "@/src/api";
import { Chip, FONT_TEXT, useToast } from "@/src/components/ui";

const LUNCH = ["", "11:15", "11:30", "11:45", "12:00", "closed"];
const EVENING = ["", "17:15", "17:30", "17:45", "18:00", "closed"];

/** Manager quick control on the dashboard: "Première livraison disponible" per service.
 *  Collapsible so the time-slot chips never mix with the order queue on phones. */
export function FirstDeliveryControl({ defaultOpen = false }: { defaultOpen?: boolean }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const { data } = useMenu();
  const set = useSetFirstDelivery();
  const [open, setOpen] = useState(defaultOpen);
  const fd = data?.settings.first_delivery ?? {};
  const label = (v: string, openAt: string) => (v === "" ? `${t("opening")} ${openAt}` : v === "closed" ? t("closedF") : v);
  const summary = `${t("lunch")} ${label(fd.lunch ?? "", "11:00")} · ${t("evening")} ${label(fd.evening ?? "", "17:00")}`;
  const row = (key: "lunch" | "evening", opts: string[], openAt: string) => (
    <View style={styles.row}>
      <Text style={styles.label}>{key === "lunch" ? t("lunch") : t("evening")}</Text>
      <View style={styles.chips}>
        {opts.map((v) => (
          <Chip key={v || "open"} label={label(v, openAt)} selected={(fd[key] ?? "") === v} onPress={() => set.mutateAsync({ [key]: v }).then(() => toast.show(t("saved"), "success")).catch((e) => toast.show(e.message, "error"))} testID={`first-delivery-${key}-${v || "open"}`} />
        ))}
      </View>
    </View>
  );
  return (
    <View style={styles.wrap} testID="first-delivery-control">
      <Pressable testID="first-delivery-toggle" onPress={() => setOpen((v) => !v)} style={styles.head}>
        <Feather name="truck" size={16} color={colors.muted} />
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>{t("firstDelivery")}</Text>
          <Text style={styles.summary} numberOfLines={1} testID="first-delivery-summary">{summary}</Text>
        </View>
        <Feather name={open ? "chevron-up" : "chevron-down"} size={20} color={colors.muted} />
      </Pressable>
      {open ? (
        <View style={styles.body}>
          {row("lunch", LUNCH, "11:00")}
          {row("evening", EVENING, "17:00")}
        </View>
      ) : null}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  wrap: { marginHorizontal: 12, marginBottom: 8, borderRadius: 14, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary },
  head: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 14, minHeight: 52 },
  title: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "800", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8 },
  summary: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "700", color: colors.onSurface, marginTop: 1 },
  body: { paddingHorizontal: 14, paddingBottom: 12, gap: 10, borderTopWidth: 1, borderTopColor: colors.divider, paddingTop: 10 },
  row: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  chips: { flex: 1, flexDirection: "row", flexWrap: "wrap", gap: 6 },
  label: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "800", color: colors.onSurface, width: 40, paddingTop: 10 },
}));
