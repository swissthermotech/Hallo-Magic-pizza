import React from "react";
import { ActivityIndicator, Platform, ScrollView, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { usePrintTicket, useTicket } from "@/src/api";
import { fmtTime } from "@/src/format";
import { Badge, Button, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";

export default function TicketScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const toast = useToast();
  const { data, isLoading } = useTicket(id);
  const print = usePrintTicket();

  const doPrint = (force: boolean) =>
    print.mutateAsync({ id: id!, force }).then(() => toast.show(t("printed"), "success")).catch((e) => toast.show(e.message, "error"));

  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("ticketPreview")} subtitle={data ? `#${data.order_number} · Epson TM-T70II (PrintNode)` : undefined} testID="ticket-title" right={data ? <Badge label={data.printed ? `${t("printed")} ${data.print_attempts}x` : t("notPrinted")} tone={data.printed ? "success" : "warning"} testID="ticket-print-status" /> : undefined} />
      {isLoading || !data ? (
        <View style={styles.center}><ActivityIndicator color={colors.brandPrimary} /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 20, alignItems: "center", paddingBottom: insets.bottom + 120 }}>
          <View style={styles.paper} testID="ticket-paper">
            <Text style={styles.mono} testID="ticket-text">{data.text}</Text>
            <View style={styles.tear} />
          </View>
          <Text style={styles.meta}>{data.printed ? `${t("printed")}: ${fmtTime(data.printed_at)} · ${data.print_attempts} ${t("printTicket").toLowerCase()}` : t("notPrinted")}</Text>
        </ScrollView>
      )}
      {data ? (
        <View style={[styles.cta, { paddingBottom: insets.bottom + 12 }]}>
          <Button title={t("printTicket")} icon="printer" size="lg" disabled={data.printed} loading={print.isPending} onPress={() => doPrint(false)} style={{ flex: 1 }} testID="ticket-print-button" />
          <Button title={t("reprintTicket")} icon="refresh-cw" size="lg" variant="outline" loading={print.isPending} onPress={() => doPrint(true)} style={{ flex: 1 }} testID="ticket-reprint-button" />
        </View>
      ) : null}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surfaceTertiary },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  paper: { width: 302, backgroundColor: colors.ticketPaper, paddingVertical: 18, paddingHorizontal: 12, shadowColor: colors.surfaceInverse, shadowOpacity: 0.15, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 4 },
  mono: { fontFamily: Platform.select({ ios: "Courier New", android: "monospace", default: "Courier New, monospace" }), fontSize: 12.5, lineHeight: 17, color: colors.onSurface },
  tear: { height: 1, borderTopWidth: 2, borderStyle: "dashed", borderColor: colors.borderStrong, marginTop: 12 },
  meta: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted, marginTop: 14 },
  cta: { position: "absolute", left: 0, right: 0, bottom: 0, flexDirection: "row", gap: 10, paddingHorizontal: 16, paddingTop: 12, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
}));
