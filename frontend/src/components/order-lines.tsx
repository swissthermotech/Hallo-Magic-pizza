import React from "react";
import { Text, View } from "react-native";
import { makeStyles } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { chf } from "@/src/format";
import { FONT_TEXT } from "./ui";
import type { OrderItem } from "@/src/types";

/** Renders order lines with removed ingredients (red, strikethrough) and extras (green). */
export function OrderLines({ items, size = "md", showPrices = true, lang }: { items: OrderItem[]; size?: "md" | "lg"; showPrices?: boolean; lang?: "fr" | "de" }) {
  const styles = useStyles();
  const i18n = useI18n();
  const tx = (v: { fr: string; de: string }) => (lang ? v[lang] : i18n.tx(v));
  const big = size === "lg";
  return (
    <View style={{ gap: big ? 14 : 10 }}>
      {items.map((it, idx) => (
        <View key={idx} style={styles.line} testID={`order-line-${idx}`}>
          <View style={[styles.qtyBox, big && styles.qtyBoxLg]}>
            <Text style={[styles.qty, big && styles.qtyLg]}>{it.quantity}x</Text>
          </View>
          <View style={{ flex: 1 }}>
            <View style={styles.nameRow}>
              <Text style={[styles.name, big && styles.nameLg]}>{tx(it.name)}{it.size ? ` ${it.size.label}` : ""}</Text>
              {showPrices ? <Text style={styles.price}>{chf(it.line_total)}</Text> : null}
            </View>
            {(it.options || []).map((o) => (
              <Text key={o.key} style={[styles.option, big && styles.modLg]}>* {tx(o.name).toUpperCase()}</Text>
            ))}
            {it.removed_ingredients.map((r) => (
              <Text key={r.id} style={[styles.removed, big && styles.modLg]}>− {i18n.t("without").toUpperCase()} {tx(r).toUpperCase()}</Text>
            ))}
            {it.extras.map((e) => (
              <Text key={e.extra_id} style={[styles.extra, big && styles.modLg]}>
                + {e.quantity > 1 ? `${e.quantity}x ` : ""}{tx(e.name)}{showPrices ? `  ${chf(e.unit_price * e.quantity)}` : ""}
              </Text>
            ))}
            {it.note ? <Text style={[styles.note, big && styles.modLg]}>NOTE: {it.note}</Text> : null}
          </View>
        </View>
      ))}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  line: { flexDirection: "row", gap: 10 },
  qtyBox: { minWidth: 34, height: 26, borderRadius: 6, backgroundColor: colors.surfaceInverse, alignItems: "center", justifyContent: "center", paddingHorizontal: 6 },
  qtyBoxLg: { minWidth: 44, height: 34 },
  qty: { fontFamily: FONT_TEXT, fontWeight: "800", color: colors.onSurfaceInverse, fontSize: 14 },
  qtyLg: { fontSize: 18 },
  nameRow: { flexDirection: "row", justifyContent: "space-between", gap: 8 },
  name: { fontFamily: FONT_TEXT, fontSize: 16, fontWeight: "700", color: colors.onSurface, flex: 1 },
  nameLg: { fontSize: 22 },
  price: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "600", color: colors.onSurface },
  removed: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.error, fontWeight: "700", marginTop: 3 },
  option: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.brandTertiary, fontWeight: "700", marginTop: 3 },
  extra: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.brandSecondary, fontWeight: "700", marginTop: 3 },
  note: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.warning, fontWeight: "700", marginTop: 3, fontStyle: "italic" },
  modLg: { fontSize: 18 },
}));
